import { Excalidraw } from "@excalidraw/excalidraw";
import "@excalidraw/excalidraw/index.css";
import { useState, useEffect } from "react";

interface ExcalidrawCanvasProps {
  onClose: () => void;
  onSave?: (data: any) => void;
  onSubmit?: (data: any) => void;
  timeLimitSeconds?: number;
}

export function ExcalidrawCanvas({ onClose, onSave, onSubmit, timeLimitSeconds = 900 }: ExcalidrawCanvasProps) {
  const [excalidrawAPI, setExcalidrawAPI] = useState<any>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isSubmitHovered, setIsSubmitHovered] = useState(false);
  const [timeLeft, setTimeLeft] = useState(timeLimitSeconds);

  useEffect(() => {
    if (timeLeft <= 0) {
      if (excalidrawAPI) {
        const elements = excalidrawAPI.getSceneElements();
        onSave?.({ elements });
      }
      onClose();
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft(prev => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [timeLeft, onClose, excalidrawAPI, onSave]);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const isWarning = timeLeft <= 60;

  return (
    <div
      className="excalidraw-modal"
      onPointerDown={(e) => e.stopPropagation()}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        zIndex: 999999,
        background: "#ffffff",
        margin: 0,
        padding: 0,
        overflow: "hidden"
      }}
    >
      <Excalidraw
        excalidrawAPI={(api) => setExcalidrawAPI(api)}
        theme="light"
        UIOptions={{
          canvasActions: {
            saveAsImage: true,
            export: {
              saveFileToDisk: true,
            },
            toggleTheme: true,
          }
        }}
      />

      <div style={{
        position: "absolute",
        top: "24px",
        right: "24px",
        zIndex: 1000000,
        display: "flex",
        gap: "12px",
        alignItems: "center"
      }}>
        <div style={{
          background: isWarning ? "rgba(255, 68, 68, 0.1)" : "rgba(115, 83, 246, 0.1)",
          color: isWarning ? "#ff4444" : "#7353F6",
          border: `1px solid ${isWarning ? "rgba(255, 68, 68, 0.3)" : "rgba(115, 83, 246, 0.3)"}`,
          padding: "10px 20px",
          borderRadius: "12px",
          fontWeight: "700",
          fontSize: "1.2rem",
          letterSpacing: "2px",
          fontVariantNumeric: "tabular-nums",
          boxShadow: "0 8px 16px rgba(0,0,0,0.1)",
        }}>
          {formatTime(timeLeft)}
        </div>

        <button
          onClick={() => {
            if (excalidrawAPI) {
              const elements = excalidrawAPI.getSceneElements();
              onSubmit?.({ elements });
            }
          }}
          onMouseEnter={() => setIsSubmitHovered(true)}
          onMouseLeave={() => setIsSubmitHovered(false)}
          style={{
            padding: "12px 24px",
            background: "#7353F6",
            color: "white",
            border: "none",
            borderRadius: "12px",
            cursor: "pointer",
            fontWeight: "700",
            fontSize: "0.9rem",
            letterSpacing: "0.5px",
            boxShadow: isSubmitHovered ? "0 12px 24px rgba(115, 83, 246, 0.3)" : "0 8px 16px rgba(115, 83, 246, 0.2)",
            transition: "all 0.2s ease",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transform: isSubmitHovered ? "translateY(-2px)" : "translateY(0)"
          }}
        >
          Submit Drawing
        </button>

        <button
          onClick={() => {
            if (excalidrawAPI) {
              const elements = excalidrawAPI.getSceneElements();
              onSave?.({ elements });
            }
            onClose();
          }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          style={{
            padding: "12px 24px",
            background: "#1a1a1a",
            color: "white",
            border: "none",
            borderRadius: "12px",
            cursor: "pointer",
            fontWeight: "700",
            fontSize: "0.9rem",
            letterSpacing: "0.5px",
            boxShadow: isHovered ? "0 12px 24px rgba(0,0,0,0.2)" : "0 8px 16px rgba(0,0,0,0.15)",
            transition: "all 0.2s ease",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            transform: isHovered ? "translateY(-2px)" : "translateY(0)"
          }}
        >
          Exit Whiteboard
        </button>
      </div>
    </div>
  );
}
