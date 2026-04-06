package main

import (
	"encoding/json"
	"log"
	"strings"
	"sync"

	"github.com/redis/go-redis/v9"
)



// Hub maintains the set of active clients and handles communication
type Hub struct {
	// Registered clients by interview UUID
	clients map[string]*Client

	// Inbound messages from the clients
	broadcast chan []byte

	// Register requests from the clients
	register chan *Client

	// Unregister requests from clients
	unregister chan *Client

	mu sync.RWMutex
}

func NewHub() *Hub {
	return &Hub{
		broadcast:  make(chan []byte),
		register:   make(chan *Client),
		unregister: make(chan *Client),
		clients:    make(map[string]*Client),
	}
}

func (h *Hub) Run() {
	// Start Redis listener for backend updates
	pubsub := rdb.PSubscribe(ctx, "interview_updates:*")
	go func() {
		defer pubsub.Close()
		ch := pubsub.Channel()
		for msg := range ch {
			h.handleRedisMessage(msg)
		}
	}()

	for {
		select {
		case client := <-h.register:
			h.mu.Lock()
			h.clients[client.interviewID] = client
			h.mu.Unlock()
		case client := <-h.unregister:
			h.mu.Lock()
			if _, ok := h.clients[client.interviewID]; ok {
				delete(h.clients, client.interviewID)
				close(client.send)
			}
			h.mu.Unlock()
		}
	}
}

func (h *Hub) handleRedisMessage(msg *redis.Message) {
	// Channel is interview_updates:<uuid>
	if !strings.HasPrefix(msg.Channel, "interview_updates:") {
		return
	}
	interviewID := strings.TrimPrefix(msg.Channel, "interview_updates:")

	log.Printf("Redis Pub/Sub: Received message for Interview %s", interviewID)

	client := h.GetClient(interviewID)
	if client == nil {
		log.Printf("Redis Pub/Sub: No active client found for Interview %s", interviewID)
		return
	}

	// Payload is the JSON from Django
	var event BaseEvent
	if err := json.Unmarshal([]byte(msg.Payload), &event); err != nil {
		log.Printf("Redis Pub/Sub: Failed to unmarshal payload: %v", err)
		return
	}

	if event.Type == TypeAiEvaluated {
		log.Printf("Redis Pub/Sub: AI Evaluation finalized for client %s (stored in DB)", interviewID)
	} else if event.Type == TypeQuestionsReady {
		log.Printf("Redis Pub/Sub: Pushing QUESTIONS_READY triggering first question to client %s", interviewID)
		client.handleNextQuestion()
	}
}



func (h *Hub) GetClient(interviewID string) *Client {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.clients[interviewID]
}
