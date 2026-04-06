package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"

	"github.com/gorilla/websocket"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 1024 * 1024 // 1MB for whiteboard JSON
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  2048,
	WriteBufferSize: 2048,
	CheckOrigin: func(r *http.Request) bool {
		return true // Allow all for now
	},
}

type Client struct {
	hub *Hub

	conn *websocket.Conn

	// Buffered channel of outbound messages.
	send chan []byte

	interviewID string

	django *DjangoClient

	questions []QuestionResponse // Cached questions to avoid re-fetching from Django
}

func (c *Client) readPump() {
	defer func() {
		c.hub.unregister <- c
		c.conn.Close()
	}()

	c.conn.SetReadLimit(maxMessageSize)
	c.conn.SetReadDeadline(time.Now().Add(pongWait))
	c.conn.SetPongHandler(func(string) error {
		c.conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	for {
		_, message, err := c.conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("error: %v", err)
			}
			break
		}

		c.handleEvent(message)
	}
}

func (c *Client) writePump() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.conn.Close()
	}()

	for {
		select {
		case message, ok := <-c.send:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				c.conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := c.conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			// Add queued chat messages to the current websocket message.
			n := len(c.send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-c.send)
			}

			if err := w.Close(); err != nil {
				return
			}
		case <-ticker.C:
			c.conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := c.conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}

func (c *Client) handleEvent(message []byte) {
	var event BaseEvent
	if err := json.Unmarshal(message, &event); err != nil {
		log.Printf("unmarshal error: %v", err)
		return
	}

	switch event.Type {
	case TypeWhiteboardSync:
		c.storeWhiteboardData(event.Data)
	case TypeSubmitAnswer:
		var data SubmitAnswerData
		if err := json.Unmarshal(event.Data, &data); err != nil {
			c.sendError("invalid submit data")
			return
		}
		c.handleSubmitAnswer(data)
	case TypeNextQuestion:
		c.handleNextQuestion()
	}
}

func (c *Client) storeWhiteboardData(data json.RawMessage) {
	state, err := GetSessionState(c.interviewID)
	if err != nil || state == nil {
		return
	}
	state.WhiteboardData = data
	SaveSessionState(*state)
}

func (c *Client) handleSubmitAnswer(data SubmitAnswerData) {
	// Handoff to Django (this triggers the background AI task)
	// We do this in a goroutine to not block the transition to the next question!
	go func() {
		_, err := c.django.SubmitAnswer(data.QuestionID, data.Answer, data.WhiteboardData)
		if err != nil {
			log.Printf("Background submit error: %v", err)
		}
	}()

	// PROCEED IMMEDIATELY TO NEXT QUESTION (latency-sensitive)
	log.Printf("Go Server: Fast-tracking to next question for %s", c.interviewID)
	
	state, _ := GetSessionState(c.interviewID)
	if state == nil {
		// Recovery if state lost
		c.handleNextQuestion()
		return
	}
	
	// Increment order in local state and find next
	nextOrder := state.SequenceOrder + 1
	c.pushNextQuestion(nil, nextOrder)
}

func (c *Client) handleNextQuestion() {
	// Load the interview only if questions are not cached
	if len(c.questions) == 0 {
		interview, err := c.django.GetInterview(c.interviewID)
		if err != nil {
			c.sendError("Failed to fetch next question")
			return
		}
		c.questions = interview.Questions
	}

	state, _ := GetSessionState(c.interviewID)
	var currentOrder int
	if state != nil {
		currentOrder = state.SequenceOrder
	} else {
		currentOrder = 1
	}

	c.pushNextQuestion(nil, currentOrder)
}

func (c *Client) pushNextQuestion(unused *InterviewResponse, nextOrder int) {
	// Use cached questions to find the target one
	if len(c.questions) == 0 {
		// Re-fetch once if still empty (maybe they just became ready)
		interview, _ := c.django.GetInterview(c.interviewID)
		if interview != nil {
			c.questions = interview.Questions
		}
	}

	var nextQ *QuestionResponse
	for _, q := range c.questions {
		if q.SequenceOrder == nextOrder {
			nextQ = &q
			break
		}
	}

	if nextQ == nil {
		if len(c.questions) == 0 {
			log.Printf("Interview %s has 0 questions ready. Waiting for background AI generation.", c.interviewID)
			return
		}
		// No more questions
		c.sendEvent(BaseEvent{Type: "INTERVIEW_COMPLETE", Data: json.RawMessage(`{}`)})
		return
	}

	// Update Redis/Session State
	SaveSessionState(SessionState{
		InterviewID:       c.interviewID,
		CurrentQuestionID: nextQ.ID,
		SequenceOrder:     nextQ.SequenceOrder,
		Status:            "IN_PROGRESS",
	})

	// Push to client
	startData := QuestionStartData{
		QuestionID:       nextQ.ID,
		QuestionText:     nextQ.QuestionText,
		SequenceOrder:    nextQ.SequenceOrder,
		Type:             nextQ.Type,
		WhiteboardEnable: nextQ.Type == "WHITEBOARD",
	}
	dataBytes, _ := json.Marshal(startData)
	c.sendEvent(BaseEvent{Type: TypeQuestionStart, Data: dataBytes})
}

func (c *Client) sendEvent(event BaseEvent) {
	bytes, _ := json.Marshal(event)
	c.send <- bytes
}

func (c *Client) sendError(msg string) {
	errData := ErrorData{Message: msg}
	dataBytes, _ := json.Marshal(errData)
	c.sendEvent(BaseEvent{Type: TypeError, Data: dataBytes})
}

func serveWs(hub *Hub, w http.ResponseWriter, r *http.Request, django *DjangoClient) {
	interviewID := r.URL.Query().Get("uuid")
	if interviewID == "" {
		http.Error(w, "uuid is required", http.StatusBadRequest)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println(err)
		return
	}

	client := &Client{
		hub:         hub,
		conn:        conn,
		send:        make(chan []byte, 256),
		interviewID: interviewID,
		django:      django,
	}
	client.hub.register <- client

	// Start pumps
	go client.writePump()
	go client.readPump()

	// Perform handshake: fetch interview from Django/Redis
	client.handleHandshake()
}

func (c *Client) handleHandshake() {
	// Check Redis first
	state, err := GetSessionState(c.interviewID)
	if err != nil {
		log.Printf("redis error: %v", err)
	}

	interview, err := c.django.GetInterview(c.interviewID)
	if err != nil {
		c.sendError("Failed to load interview from Django")
		return
	}

	var currentOrder int
	if state != nil {
		currentOrder = state.SequenceOrder
	} else {
		currentOrder = 1 // Start with first question
	}

	c.pushNextQuestion(interview, currentOrder)
}
