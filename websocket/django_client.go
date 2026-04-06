package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
)


const DjangoBaseURL = "http://localhost:8000"

type DjangoClient struct {
	BaseURL string
}

func NewDjangoClient() *DjangoClient {
	return &DjangoClient{BaseURL: DjangoBaseURL}
}

// InterviewResponse matches the Django InterviewSerializer
type InterviewResponse struct {
	ID        string             `json:"id"`
	Status    string             `json:"status"`
	Questions []QuestionResponse `json:"questions"`
}

// QuestionResponse matches the Django QuestionSerializer
type QuestionResponse struct {
	ID            int    `json:"id"`
	QuestionText  string `json:"question_text"`
	SequenceOrder int    `json:"sequence_order"`
	Type          string `json:"type"`
	Status        string `json:"status"`
}

func (c *DjangoClient) GetInterview(uuid string) (*InterviewResponse, error) {
	resp, err := http.Get(fmt.Sprintf("%s/api/interviews/%s/", c.BaseURL, uuid))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("django returned status %d", resp.StatusCode)
	}

	var interview InterviewResponse
	if err := json.NewDecoder(resp.Body).Decode(&interview); err != nil {
		return nil, err
	}
	return &interview, nil
}

func (c *DjangoClient) SubmitAnswer(questionID int, answer string, whiteboardData json.RawMessage) (*QuestionResponse, error) {
	payload := map[string]interface{}{
		"question_id":     questionID,
		"answer":          answer,
		"whiteboard_data": whiteboardData,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	log.Printf("Django Client: Submitting answer for Question %d to %s", questionID, c.BaseURL)
	resp, err := http.Post(
		fmt.Sprintf("%s/api/internal/submit-answer/", c.BaseURL),
		"application/json",
		bytes.NewBuffer(data),
	)

	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := ioutil.ReadAll(resp.Body)
		return nil, fmt.Errorf("django returned status %d: %s", resp.StatusCode, string(body))
	}

	var question QuestionResponse
	if err := json.NewDecoder(resp.Body).Decode(&question); err != nil {
		return nil, err
	}
	return &question, nil
}
