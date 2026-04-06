import { Canvas, useFrame, useThree } from '@react-three/fiber'
import {
  Environment,
  PointerLockControls,
  Gltf,
  Text,
  KeyboardControls,
  useKeyboardControls,
  AdaptiveDpr,
  Preload,
  BakeShadows
} from '@react-three/drei'
import { Physics, RigidBody, CapsuleCollider } from '@react-three/rapier'
import { EffectComposer, Bloom, N8AO } from '@react-three/postprocessing'
import { Suspense, useState, useCallback, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import * as THREE from 'three'
import { InterviewerWithDesk as Interviewer } from './components/InterviewerWithDesk'
import { ExcalidrawCanvas } from './components/ExcalidrawCanvas'
import { Dashboard } from './components/Dashboard'
import './App.css'

const MOVE_SPEED = 5
const WS_URL = 'ws://localhost:8080/ws'
const API_URL = 'http://localhost:8000/api'

// --- Types ---

interface Question {
  question_id: number;
  question_text: string;
  sequence_order: number;
  type: string;
  whiteboard_enable: boolean;
}

interface InterviewReport {
  aggregate_score: number;
  summary_feedback: string;
  total_questions: number;
  evaluated_questions: number;
}

interface TranscriptMessage {
  id: string;
  sender: 'SYSTEM' | 'USER';
  text: string;
  timestamp: Date;
}

// --- Typewriter Subtitle Component ---
function TypewriterSubtitle({ sender, text, durationMs }: { sender: 'SYSTEM' | 'USER', text: string, durationMs: number }) {
  const words = text.split(' ')
  const [isStarted, setIsStarted] = useState(sender === 'USER')
  const [displayText, setDisplayText] = useState(text)
  const lastTextRef = useRef(text)

  // Windowed transcription for USER
  useEffect(() => {
    if (sender !== 'USER') {
      setDisplayText(text)
      return
    }
    const words = text.split(' ')
    // Limit to roughly last 22 words to guarantee staying under 2 lines on 1000px width
    if (words.length > 22) {
      setDisplayText('... ' + words.slice(-22).join(' '))
    } else {
      setDisplayText(text)
    }
  }, [text, sender])

  useEffect(() => {
    if (sender === 'USER') {
      setIsStarted(true)
      return
    }

    // Only trigger typewriter flip if text is actually new
    if (text !== lastTextRef.current) {
      setIsStarted(false)
      const timer = setTimeout(() => {
        setIsStarted(true)
        lastTextRef.current = text
      }, 50)
      return () => clearTimeout(timer)
    } else if (!isStarted) {
      setIsStarted(true)
    }
  }, [text, sender, isStarted])

  // Total duration for the full text reveal matches audio duration
  // If USER, set a small fixed duration so words appear quickly but naturally
  const revealDuration = sender === 'USER' ? 0 : Math.max(1, durationMs - 500)

  return (
    <div className={`subtitle-overlay ${!isStarted ? 'hidden' : ''}`}>
      <div className="subtitle-text">
        {sender === 'USER' ? (
          /* Plain text for user transcription to prevent lag during rapid updates */
          displayText
        ) : (
          words.map((word, i) => {
            const delay = (i / words.length) * revealDuration
            return (
              <span
                key={`${sender}-${i}`}
                className="subtitle-word"
                style={{
                  '--word-delay': `${delay}ms`,
                  '--word-index': i
                } as React.CSSProperties}
              >
                {word}
              </span>
            )
          })
        )}
      </div>
    </div>
  )
}

// --- Audio Logic Placeholders (Future STT/TTS Injection Points) ---

let currentAudioInstance: HTMLAudioElement | null = null;
const AudioService = {
  stopAudio: () => {
    if (currentAudioInstance) {
      currentAudioInstance.pause();
      currentAudioInstance.src = '';
      currentAudioInstance = null;
    }
  },
  /**
   * Text-to-Speech.
   * Speaks text and returns the audio duration in ms.
   * Calls onStart() the instant audio begins playing.
   */
  handleSystemResponse: async (text: string): Promise<number> => {
    console.log(`TTS output for: "${text.substring(0, 50)}..."`);
    // Stop any current audio before playing a new one
    AudioService.stopAudio();
    
    try {
      const response = await fetch(`${API_URL}/speak/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });

      if (!response.ok) throw new Error('TTS failed');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudioInstance = audio;

      return new Promise<number>((resolve) => {
        audio.onloadedmetadata = () => {
          const duration = Math.round((audio.duration || 3) * 1000);
          audio.play();
          resolve(duration);
        };
        audio.onended = () => {
          URL.revokeObjectURL(url);
          if (currentAudioInstance === audio) currentAudioInstance = null;
        };
        audio.onerror = () => {
          URL.revokeObjectURL(url);
          if (currentAudioInstance === audio) currentAudioInstance = null;
          resolve(3000);
        };
        audio.load();
      });
    } catch (err) {
      console.error('TTS Error:', err);
      return 3000;
    }
  }
};

// --- Components ---

function PhysicalPlayer({ enabled = true }: { enabled?: boolean }) {
  const rb = useRef<any>(null)
  const [, getKeys] = useKeyboardControls()
  const { camera } = useThree()

  // Set initial spawn rotation to face the interviewer
  useEffect(() => {
    // Math.PI + Math.PI/12 faces roughly towards the interviewer at (-11, 0, 1) from (-2, 0, 0)
    camera.rotation.set(0, Math.PI / 2, 0)
  }, [camera])

  useFrame((_state, delta) => {
    if (!rb.current || !enabled) return

    const { forward, backward, left, right } = getKeys()

    // Get movement direction relative to camera looking forward
    const direction = new THREE.Vector3()
    const frontVector = new THREE.Vector3(0, 0, (backward ? 1 : 0) - (forward ? 1 : 0))
    const sideVector = new THREE.Vector3((left ? 1 : 0) - (right ? 1 : 0), 0, 0)

    direction
      .subVectors(frontVector, sideVector)
      .normalize()
      .multiplyScalar(MOVE_SPEED)
      .applyQuaternion(camera.quaternion)

    // Current linear velocity
    const velocity = rb.current.linvel()

    // Apply movement while preserving vertical velocity (for gravity)
    rb.current.setLinvel({ x: direction.x, y: velocity.y, z: direction.z }, true)

    // Lock camera to player position with 1.3 height offset
    const translation = rb.current.translation()
    camera.position.set(translation.x, translation.y + 0.5, translation.z)
  })

  return (
    <>
      <RigidBody
        ref={rb}
        colliders={false}
        mass={1}
        type="dynamic"
        position={[-2, 1.6, 0]} // Spawning well above the floor to avoid clipping issues
        enabledRotations={[false, false, false]}
        friction={0} // Zero friction on the player to allow smooth sliding and prevent getting stuck
        linearDamping={0.5}
        angularDamping={0.5}
        restitution={0}
      >
        <CapsuleCollider args={[0.7, 0.4]} />
      </RigidBody>
      {enabled && <PointerLockControls />}
    </>
  )
}

function WhiteboardInteraction({ onPlayerProximity }: { onPlayerProximity: (near: boolean) => void }) {
  const WHITEBOARD_POSITION = new THREE.Vector3(-6, 0.3, -4)
  const PROXIMITY_THRESHOLD = 2.5
  const { camera } = useThree()

  useFrame(() => {
    const dist = camera.position.distanceTo(WHITEBOARD_POSITION)
    onPlayerProximity(dist < PROXIMITY_THRESHOLD)
  })

  return null
}

function InterviewerInteraction({ onPlayerProximity }: { onPlayerProximity: (near: boolean) => void }) {
  const INTERVIEWER_POSITION = new THREE.Vector3(-11, 0.3, 1) // Match the interviewer's position
  const PROXIMITY_THRESHOLD = 3.5
  const { camera } = useThree()

  useFrame(() => {
    const dist = camera.position.distanceTo(INTERVIEWER_POSITION)
    onPlayerProximity(dist < PROXIMITY_THRESHOLD)
  })

  return null
}

function InterviewScene({ isAnimating, questionText, onWhiteboardProximity, isWhiteboardOpen, onInterviewerProximity }: {
  isAnimating: boolean,
  questionText?: string,
  onWhiteboardProximity: (near: boolean) => void,
  isWhiteboardOpen: boolean,
  onInterviewerProximity: (near: boolean) => void
}) {
  return (
    <>
      <Physics gravity={[0, 0, 0]}>
        <ambientLight intensity={0.4} color="#eef" />
        <spotLight
          position={[5, 8, 5]}
          angle={0.4}
          penumbra={1}
          intensity={200}
          castShadow
          shadow-bias={-0.0001}
        />
        <pointLight position={[0, 4, -2]} intensity={50} color="#fff" />

        <Suspense fallback={null}>
          <RigidBody type="fixed" colliders="trimesh">
            <Gltf src="/model/room.glb" scale={1} position={[0, 0, 0]} receiveShadow castShadow />
          </RigidBody>

          {/* Solid Floor Plane with extreme thickness (5 units) to prevent falling through */}
          <RigidBody type="fixed" colliders="cuboid" friction={0.5}>
            <mesh position={[0, -2.6, 0]}>
              <boxGeometry args={[200, 5, 200]} />
              <meshStandardMaterial visible={false} />
            </mesh>
          </RigidBody>


          <Interviewer scale={0.24} position={[-12, 0.1, 0]} rotation={[0, 0, 0]} />

          <Gltf src="/model/whiteboard.glb" scale={0.7} position={[-6, 0.3, -4]} rotation={[0, Math.PI / 2, 0]} castShadow receiveShadow />

          {questionText && (
            <Text
              position={[1.8, 1.5, -0.3]}
              rotation={[0, -Math.PI / 4, 0]}
              fontSize={0.08}
              maxWidth={1.5}
              color="black"
              anchorX="center"
              anchorY="middle"
            >
              {questionText}
            </Text>
          )}

          <Environment preset="city" background blur={0.1} />
        </Suspense>

        <PhysicalPlayer enabled={!isWhiteboardOpen} />
        <WhiteboardInteraction onPlayerProximity={onWhiteboardProximity} />
        <InterviewerInteraction onPlayerProximity={onInterviewerProximity} />
      </Physics>

      <EffectComposer enableNormalPass>
        <N8AO intensity={2} aoRadius={0.2} />
        <Bloom luminanceThreshold={1.2} intensity={0.5} levels={9} mipmapBlur />
      </EffectComposer>

      <BakeShadows />
      <Preload all />
    </>
  )
}

function App() {
  const [isInterviewStarted, setIsInterviewStarted] = useState(false)
  const [isLoadingAssets, setIsLoadingAssets] = useState(false)
  const [loadingProgress, setLoadingProgress] = useState(0)
  const [loadingMessage, setLoadingMessage] = useState('Initializing...')

  // Ingestion State (Lifted from Dashboard)
  const [jdText, setJdText] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [jdFileName, setJdFileName] = useState('');
  const [resumeFileName, setResumeFileName] = useState('');
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdLoading, setJdLoading] = useState(false);
  const [jdProgress, setJdProgress] = useState(0);

  const [interviewId, setInterviewId] = useState<string | null>(null)
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [report, setReport] = useState<InterviewReport | null>(null)
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([])
  const [status, setStatus] = useState<'IDLE' | 'CONNECTING' | 'IN_PROGRESS' | 'EVALUATING' | 'COMPLETED'>('IDLE')
  const [nearWhiteboard, setNearWhiteboard] = useState(false)
  const [isWhiteboardOpen, setIsWhiteboardOpen] = useState(false)
  const [nearInterviewer, setNearInterviewer] = useState(false)
  const [isResumeModalOpen, setIsResumeModalOpen] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [recordedText, setRecordedText] = useState('')
  const [toast, setToast] = useState<{ message: string; type: 'error' | 'info' } | null>(null)
  const [isWhiteboardTask, setIsWhiteboardTask] = useState(false)
  const [lastWhiteboardData, setLastWhiteboardData] = useState<any>(null)
  const [activeSubtitle, setActiveSubtitle] = useState<{ sender: 'SYSTEM' | 'USER', text: string, durationMs: number } | null>(null)
  const [showWhiteboardIndicator, setShowWhiteboardIndicator] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const recognitionRef = useRef<any>(null)
  const interactionLogRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (interactionLogRef.current) {
      interactionLogRef.current.scrollTop = interactionLogRef.current.scrollHeight
    }
  }, [transcript, status])

  const addTranscriptEntry = useCallback((sender: 'SYSTEM' | 'USER', text: string) => {
    setTranscript(prev => [...prev, {
      id: Math.random().toString(36).substr(2, 9),
      sender,
      text,
      timestamp: new Date()
    }])
  }, [])

  useEffect(() => {
    if (isWhiteboardOpen || isResumeModalOpen) {
      document.exitPointerLock?.()
    }
  }, [isWhiteboardOpen, isResumeModalOpen])

  // Sync real-time transcription to general subtitle box
  useEffect(() => {
    if (isRecording && recordedText) {
      setActiveSubtitle(prev => {
        // If the system is currently speaking, don't let the user transcription overwrite it
        if (prev?.sender === 'SYSTEM') return prev;
        return { sender: 'USER', text: recordedText, durationMs: 0 };
      });
    }
  }, [isRecording, recordedText])

  // --- STT Initialization ---
  useEffect(() => {
    const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition();
      recognition.lang = 'en-US';
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onresult = (event: any) => {
        let transcript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          transcript += event.results[i][0].transcript;
        }
        setRecordedText(transcript);
      };

      recognition.onend = () => {
        // Recognition might stop automatically if the user pauses for too long
        console.log("Recognition ended");
      };

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error);
        if (event.error === 'not-allowed') {
          showToast('Microphone access denied.', 'error');
        }
      };

      recognitionRef.current = recognition;
    }
  }, []);

  useEffect(() => {
    if (isRecording) {
      setRecordedText('');
      try {
        recognitionRef.current?.start();
      } catch (e) {
        console.warn("Recognition already started or failed to start", e);
      }
    } else {
      try {
        recognitionRef.current?.stop();
      } catch (e) {
        console.warn("Recognition already stopped", e);
      }
    }
  }, [isRecording]);

  const submitAnswer = useCallback(async (whiteboardDataOverride?: any) => {
    if (ws && currentQuestion) {
      AudioService.stopAudio(); // Interrupt any ongoing TTS
      setStatus('EVALUATING')
      setIsRecording(false);
      setShowWhiteboardIndicator(false) // Dismiss when answering
      setIsWhiteboardOpen(false); // Close whiteboard upon submission
      setActiveSubtitle(null);

      // Wait a tiny bit for the final transcript to settle
      await new Promise(r => setTimeout(r, 60));

      const userText = recordedText.trim() || "No response captured.";
      addTranscriptEntry('USER', userText);

      const payload = {
        type: 'SUBMIT_ANSWER',
        data: {
          question_id: currentQuestion.question_id,
          answer: userText,
          whiteboard_data: whiteboardDataOverride || (isWhiteboardTask ? lastWhiteboardData : null)
        }
      }
      ws.send(JSON.stringify(payload))
      setRecordedText('');
      setLastWhiteboardData(null)
      setIsWhiteboardTask(false)
    }
  }, [ws, currentQuestion, addTranscriptEntry, recordedText, isWhiteboardTask, lastWhiteboardData])

  // --- Interaction Logic ---

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Whiteboard interaction
      if (e.key.toLowerCase() === 'e' && nearWhiteboard && !isWhiteboardOpen) {
        if (document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
          setIsWhiteboardOpen(true)
        }
      }

      // Resume upload interaction near interviewer
      if (e.key.toLowerCase() === 'r' && nearInterviewer && !isResumeModalOpen && !interviewId) {
        if (document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
          setIsResumeModalOpen(true)
        }
      }

      // Spacebar to toggle recording
      if (e.code === 'Space' && status === 'IN_PROGRESS' && !isWhiteboardOpen && !isResumeModalOpen) {
        if (document.activeElement?.tagName !== 'TEXTAREA' && document.activeElement?.tagName !== 'INPUT') {
          e.preventDefault()
          if (isRecording) {
            submitAnswer()
          } else {
            AudioService.stopAudio(); // Silence the interviewer immediately
            setActiveSubtitle(null);
            setIsRecording(true)
          }
        }
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [nearWhiteboard, isWhiteboardOpen, nearInterviewer, isResumeModalOpen, interviewId, status, isRecording, submitAnswer])

  // --- WebSocket Logic ---

  const showToast = useCallback((message: string, type: 'error' | 'info' = 'info') => {
    setToast({ message, type })
    setTimeout(() => setToast(null), 5000)
  }, [])

  const speakWithSubtitle = useCallback(async (sender: 'SYSTEM' | 'USER', text: string) => {
    if (sender === 'USER') {
      setActiveSubtitle({ sender, text, durationMs: 0 });
      addTranscriptEntry(sender, text);
      return;
    }

    // Immediately clear previous subtitle
    setActiveSubtitle(null);

    // Give immediate feedback in the chat log so the user knows the AI is responding
    addTranscriptEntry(sender, text);

    // Fetch and prepare audio (this returns after audio starts playing)
    const duration = await AudioService.handleSystemResponse(text);
    
    // Start subtitle typewriter now that audio is playing for perfect sync
    setActiveSubtitle({ sender, text, durationMs: duration });

    // Clear subtitle after duration
    setTimeout(() => {
      setActiveSubtitle(prev => (prev?.text === text ? null : prev))
    }, duration + 1000)
  }, [addTranscriptEntry])

  useEffect(() => {
    if (interviewId && !wsRef.current) {
      setStatus('CONNECTING')
      const socket = new WebSocket(`${WS_URL}?uuid=${interviewId}`)

      socket.onopen = () => {
        console.log('WS Connected')
        setStatus('IN_PROGRESS')
      }

      socket.onmessage = (event) => {
        const msg = JSON.parse(event.data)
        console.log('WS Message:', msg)

        switch (msg.type) {
          case 'QUESTION_START':
            setCurrentQuestion(msg.data)
            setStatus('IN_PROGRESS')
            setIsWhiteboardTask(msg.data.whiteboard_enable)
            if (msg.data.whiteboard_enable) {
              setShowWhiteboardIndicator(true)
            }
            speakWithSubtitle('SYSTEM', msg.data.question_text)
            break
          case 'AI_EVALUATED':
            setStatus('IN_PROGRESS')
            speakWithSubtitle('SYSTEM', msg.data.feedback)
            break
          case 'INTERVIEW_COMPLETE':
            setStatus('COMPLETED')
            setCurrentQuestion(null)
            
            const fetchReport = async () => {
              try {
                const res = await fetch(`${API_URL}/interviews/${interviewId}/report/`);
                if (res.ok) {
                  const data = await res.json();
                  setReport(data);
                  if (data.total_questions > 0 && data.evaluated_questions < data.total_questions) {
                    setTimeout(fetchReport, 2000);
                  }
                }
              } catch (err) {
                console.error('Error fetching report:', err);
              }
            };
            fetchReport();

            speakWithSubtitle('SYSTEM', "The interview is now complete. You can now view and download your comprehensive evaluation report.")
            break
          case 'ERROR':
            console.error('WS Error:', msg.data.message)
            showToast(msg.data.message, 'error')
            break
        }
      }

      socket.onclose = () => {
        console.log('WS Closed')
        wsRef.current = null
      }

      wsRef.current = socket
      setWs(socket)
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [interviewId, speakWithSubtitle, showToast])

  const exitInterview = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setWs(null)
    setIsInterviewStarted(false)
    setInterviewId(null)
    setCurrentQuestion(null)
    setReport(null)
    setStatus('IDLE')
    setIsWhiteboardTask(false)
    setShowWhiteboardIndicator(false)
    setActiveSubtitle(null)
  }

  const handleCommenceInterview = async () => {
    setIsLoadingAssets(true)
    setLoadingProgress(0)

    // Simulate asset loading
    const steps = [
      { message: 'Loading environment textures...', progress: 20 },
      { message: 'Setting up physics engine...', progress: 45 },
      { message: 'Initializing interviewer AI...', progress: 70 },
      { message: 'Ready', progress: 100 },
    ]

    for (const step of steps) {
      setLoadingMessage(step.message)
      setLoadingProgress(step.progress)
      
      // Request dummy permissions (Camera & Mic) at the 70% mark
      if (step.progress === 70) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
          stream.getTracks().forEach(track => track.stop())
        } catch (e) {
          console.warn("Permission denied or not supported", e)
        }
      }

      await new Promise(r => setTimeout(r, 150 + Math.random() * 100))
    }

    // Just enter the physical room without starting backend yet.
    setIsInterviewStarted(true)
    setIsLoadingAssets(false)
  }

  const handleSubmitResumeModal = async () => {
    if (!resumeText && !resumeFile) {
      showToast('Please provide your Resume.', 'error')
      return
    }

    setIsResumeModalOpen(false)
    setIsLoadingAssets(true) // Reusing this for API call overlay
    setLoadingProgress(50)
    setLoadingMessage('Synchronizing with server...')

    try {
      const formData = new FormData();
      if (jdFile) formData.append('jd_file', jdFile);
      if (jdText) formData.append('jd_text', jdText);
      if (resumeFile) formData.append('resume_file', resumeFile);
      if (resumeText) formData.append('resume_text', resumeText);

      const resp = await fetch(`${API_URL}/interviews/`, {
        method: 'POST',
        body: formData,
      })

      if (!resp.ok) {
        const errorData = await resp.json()
        throw new Error(errorData.error || 'Server error while starting interview')
      }

      const data = await resp.json()
      setInterviewId(data.id)
      setIsLoadingAssets(false)
      showToast('Resume submitted. Establishing connection...', 'info')
    } catch (err: any) {
      console.error('Failed to start interview:', err)
      showToast(err.message || 'Failed to start interview. Please check your connection.', 'error')
      setIsLoadingAssets(false)
    }
  }

  const requestNextQuestion = () => {
    if (ws) {
      ws.send(JSON.stringify({ type: 'NEXT_QUESTION', data: {} }))
    }
  }

  if (!isInterviewStarted) {
    return (
      <>
        <Dashboard
          onCommence={handleCommenceInterview}
          isLoading={isLoadingAssets}
          loadingProgress={loadingProgress}
          loadingMessage={loadingMessage}
          showToast={showToast}

          jdText={jdText} setJdText={setJdText}
          jdFileName={jdFileName} setJdFileName={setJdFileName}
          jdFile={jdFile} setJdFile={setJdFile}
          jdLoading={jdLoading} setJdLoading={setJdLoading}
          jdProgress={jdProgress} setJdProgress={setJdProgress}
        />
        {toast && (
          <div className="toast-container">
            <div className={`toast-notification ${toast.type}`}>
              {toast.type === 'error' && (
                <div className="toast-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                </div>
              )}
              <div className="toast-message">{toast.message}</div>
              <div className="toast-close" onClick={() => setToast(null)}>✕</div>
            </div>
          </div>
        )}
      </>
    )
  }

  return (
    <KeyboardControls
      map={[
        { name: 'forward', keys: ['ArrowUp', 'w', 'W'] },
        { name: 'backward', keys: ['ArrowDown', 's', 'S'] },
        { name: 'left', keys: ['ArrowLeft', 'a', 'A'] },
        { name: 'right', keys: ['ArrowRight', 'd', 'D'] },
        { name: 'interact', keys: ['e', 'E'] },
      ]}
    >
      <div className="canvas-container">
        <Canvas shadows dpr={[1, 2]} >
          <InterviewScene
            isAnimating={status === 'EVALUATING'}
            questionText={currentQuestion?.question_text}
            onWhiteboardProximity={setNearWhiteboard}
            isWhiteboardOpen={isWhiteboardOpen}
            onInterviewerProximity={setNearInterviewer}
          />
          <AdaptiveDpr pixelated />
        </Canvas>

        {isWhiteboardOpen && createPortal(
          <ExcalidrawCanvas
            onSave={(data) => setLastWhiteboardData(data)}
            onSubmit={(data) => {
              setLastWhiteboardData(data);
              submitAnswer(data);
            }}
            onClose={() => setIsWhiteboardOpen(false)}
          />,
          document.body
        )}

        {/* Proximity Interaction Prompts */}
        {nearWhiteboard && !isWhiteboardOpen && (
          <div className="interaction-prompt" onClick={() => setIsWhiteboardOpen(true)} style={{ bottom: '100px' }}>
            <div className="click-indicator">
              <span className="key-hint">E</span>
              <span className="hint-text">Use Whiteboard</span>
            </div>
          </div>
        )}

        {nearInterviewer && !isResumeModalOpen && !interviewId && (
          <div className="interaction-prompt" onClick={() => setIsResumeModalOpen(true)} style={{ bottom: '100px' }}>
            <div className="click-indicator">
              <span className="key-hint">R</span>
              <span className="hint-text">Submit Resume</span>
            </div>
          </div>
        )}

        {isResumeModalOpen && createPortal(
          <div className="resume-modal-backdrop" onClick={() => setIsResumeModalOpen(false)}>
            <div className="resume-modal-content" onClick={e => e.stopPropagation()}>
              <h2>Submit Resume</h2>
              <p>
                Please provide your resume to start the interview session.
              </p>

              <div>
                <textarea
                  className="resume-textarea"
                  placeholder="Paste or type Resume here..."
                  value={resumeText}
                  onChange={(e) => {
                    setResumeText(e.target.value);
                    setResumeFile(null);
                  }}
                />
                <div className="resume-upload-divider">OR</div>
                <input
                  type="file"
                  id="resume-file-upload"
                  style={{ display: 'none' }}
                  accept=".pdf,.txt,.docx"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setResumeFile(file);
                      setResumeText('');
                      setResumeFileName(file.name);
                    }
                  }}
                />
                <button className="resume-file-btn" onClick={() => document.getElementById('resume-file-upload')?.click()}>
                  {resumeFile ? `Selected: ${resumeFileName}` : 'Select PDF or Text File'}
                </button>
              </div>

              <div className="resume-modal-actions">
                <button className="resume-btn-cancel" onClick={() => setIsResumeModalOpen(false)}>
                  Cancel
                </button>
                <button className="resume-btn-submit" onClick={handleSubmitResumeModal}>
                  Submit & Start
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {/* Subtitle Overlay - Replaces the interaction-log for a cleaner look */}
        {activeSubtitle && (
          <TypewriterSubtitle
            sender={activeSubtitle.sender}
            text={activeSubtitle.text}
            durationMs={activeSubtitle.durationMs || 3000}
          />
        )}

        {/* Temporary Whiteboard Indicator */}
        {showWhiteboardIndicator && (
          <div className="whiteboard-indicator-pod">
            <div className="msg">Whiteboard Available (E)</div>
            <div className="icon">
              <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </div>
          </div>
        )}

        {!isWhiteboardOpen && (
          <div className="ui-overlay">
            {/* Header Branding */}
            <header className="header" style={{ pointerEvents: 'auto' }}>
              <h1>Crack AI</h1>
              <p>Advanced Real-time Assessment</p>
            </header>

            {status === 'EVALUATING' && (
              <div className="subtitle-overlay processing">
                <div className="subtitle-text">Analyzing your verbal response...</div>
              </div>
            )}

            {status === 'IN_PROGRESS' && !currentQuestion && (
              <div className="subtitle-overlay processing">
                <div className="subtitle-text">AI is analyzing your resume and generating questions...</div>
              </div>
            )}

            {/* Voice Control Trigger */}
            {status !== 'COMPLETED' && (
              <div className="voice-control-center">
                <button
                  className={`voice-trigger ${isRecording ? 'recording' : ''}`}
                  onClick={() => {
                    if (isRecording) {
                      submitAnswer()
                    } else if (status === 'IN_PROGRESS') {
                      setIsRecording(true)
                    }
                  }}
                >
                  <div className="mic-icon">
                    <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                      <line x1="12" y1="19" x2="12" y2="23"></line>
                      <line x1="8" y1="23" x2="16" y2="23"></line>
                    </svg>
                  </div>
                  <div className="trigger-text">
                    {isRecording ? 'Submit Answer' : (status === 'EVALUATING' ? 'Evaluating...' : 'Speak Now')}
                  </div>
                </button>
              </div>
            )}

            {/* Completion & Report Screen */}
            {status === 'COMPLETED' && (
              <div className="completion-pod">
                <h2>Interview Concluded</h2>
                <p>Your comprehensive performance analysis has been generated successfully.</p>

                {report && (
                  <div className="completion-stats">
                    <div className="stat-item">
                      <div className="stat-label">Final Score</div>
                      <div className="stat-value">{report.aggregate_score || 0}/10</div>
                    </div>
                  </div>
                )}

                <div className="completion-actions">
                  <button
                    className="pdf-download-button"
                    onClick={() => window.open(`http://localhost:8000/api/interviews/${interviewId}/pdf/`, '_blank')}
                  >
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                      <polyline points="7 10 12 15 17 10"></polyline>
                      <line x1="12" y1="15" x2="12" y2="3"></line>
                    </svg>
                    Download Report
                  </button>

                  <button className="resume-btn-cancel" style={{ width: '100%', padding: '16px', fontSize: '1rem' }} onClick={exitInterview}>
                    Close Session
                  </button>
                </div>
              </div>
            )}

            {/* Exit control is always visible while in the room */}
            <div className="status-indicator">
              <div className="dot" style={{ background: ws ? '#00ff00' : '#ff0000' }} />
              {ws ? 'Live Session' : 'Offline'}

              <button
                className="exit-interview-btn"
                onClick={exitInterview}
                style={{ marginLeft: '20px', position: 'relative', top: '0', right: '0' }}
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6L6 18M6 6l12 12"></path>
                </svg>
                Exit Session
              </button>
            </div>
          </div>
        )}


        {toast && (
          <div className="toast-container">
            <div className={`toast-notification ${toast.type}`}>
              {toast.type === 'error' && (
                <div className="toast-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                </div>
              )}
              <div className="toast-message">{toast.message}</div>
              <div className="toast-close" onClick={() => setToast(null)}>✕</div>
            </div>
          </div>
        )}
      </div>
    </KeyboardControls>
  )
}

export default App

