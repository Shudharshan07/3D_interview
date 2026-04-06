package main

import "encoding/json"

// Event types
const (
	TypeQuestionStart  = "QUESTION_START"
	TypeWhiteboardSync = "WHITEBOARD_SYNC"
	TypeSubmitAnswer   = "SUBMIT_ANSWER"
	TypeAiEvaluated    = "AI_EVALUATED"
	TypeNextQuestion   = "NEXT_QUESTION"
	TypeQuestionsReady = "QUESTIONS_READY"
	TypeError          = "ERROR"
)

// BaseEvent is the common structure for all WebSocket messages
type BaseEvent struct {
	Type string          `json:"type"`
	Data json.RawMessage `json:"data"`
}

// QuestionStartData is sent from Server to Client
type QuestionStartData struct {
	QuestionID       int    `json:"question_id"`
	QuestionText     string `json:"question_text"`
	SequenceOrder    int    `json:"sequence_order"`
	Type             string `json:"type"` // TECHNICAL or WHITEBOARD
	WhiteboardEnable bool   `json:"whiteboard_enable"`
}

// WhiteboardSyncData is sent bidirectionally
type WhiteboardSyncData struct {
	Elements json.RawMessage `json:"elements"` // Excalidraw-style JSON
}

// SubmitAnswerData is sent from Client to Server
type SubmitAnswerData struct {
	QuestionID     int             `json:"question_id"`
	Answer         string          `json:"answer"`
	WhiteboardData json.RawMessage `json:"whiteboard_data,omitempty"`
}

// ErrorData is sent from Server to Client
type ErrorData struct {
	Message string `json:"message"`
}

// AiEvaluatedData (Future-proof)
type AiEvaluatedData struct {
	QuestionID int    `json:"question_id"`
	Score      int    `json:"score"`
	Feedback   string `json:"feedback"`
}
