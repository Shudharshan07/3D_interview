package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)


var (
	ctx = context.Background()
	rdb *redis.Client
)

func initRedis() {
	rdb = redis.NewClient(&redis.Options{
		Addr: "127.0.0.1:6379",
		Password: "", // no password set
		DB: 0,  // use default DB
	})

	// Check connection
	_, err := rdb.Ping(ctx).Result()
	if err != nil {
		log.Fatalf("FAILED TO CONNECT TO REDIS: %v", err)
	}
	log.Println("Successfully connected to Redis at 127.0.0.1:6379")
}


// SessionState represents the state of an interview session stored in Redis
type SessionState struct {
	InterviewID       string          `json:"interview_id"`
	CurrentQuestionID int             `json:"current_question_id"`
	SequenceOrder     int             `json:"sequence_order"`
	Status            string          `json:"status"`
	WhiteboardData    json.RawMessage `json:"whiteboard_data,omitempty"`
}

func getSessionKey(interviewID string) string {
	return fmt.Sprintf("session:%s", interviewID)
}

func SaveSessionState(state SessionState) error {
	data, err := json.Marshal(state)
	if err != nil {
		return err
	}
	return rdb.Set(ctx, getSessionKey(state.InterviewID), data, 24*time.Hour).Err()
}

func GetSessionState(interviewID string) (*SessionState, error) {
	val, err := rdb.Get(ctx, getSessionKey(interviewID)).Result()
	if err == redis.Nil {
		return nil, nil // No session found
	} else if err != nil {
		return nil, err
	}

	var state SessionState
	if err := json.Unmarshal([]byte(val), &state); err != nil {
		return nil, err
	}
	return &state, nil
}
