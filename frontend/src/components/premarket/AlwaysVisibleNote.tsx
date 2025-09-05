// src/components/premarket/AlwaysVisibleNote.tsx
import React, { useState, useEffect, useRef } from "react";

const AlwaysVisibleNote: React.FC = () => {
  const [note, setNote] = useState<string>("");
  const [position, setPosition] = useState({ x: window.innerWidth - 250, y: 10 });
  const [dragging, setDragging] = useState(false);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const boxRef = useRef<HTMLDivElement>(null);

  // Load note and position from localStorage
  useEffect(() => {
    const savedNote = localStorage.getItem("quick_note");
    if (savedNote) setNote(savedNote);

    const savedPos = localStorage.getItem("quick_note_position");
    if (savedPos) {
      try {
        const parsed = JSON.parse(savedPos);
        setPosition(parsed);
      } catch {
        // ignore bad data
      }
    }
  }, []);

  // Save note to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem("quick_note", note);
  }, [note]);

  // Save position to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem("quick_note_position", JSON.stringify(position));
  }, [position]);

  // Mouse event handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (boxRef.current && e.target === boxRef.current.querySelector(".note-header")) {
      setDragging(true);
      setOffset({
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      });
    }
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (dragging) {
      setPosition({
        x: e.clientX - offset.x,
        y: e.clientY - offset.y,
      });
    }
  };

  const handleMouseUp = () => {
    setDragging(false);
  };

  useEffect(() => {
    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  });

  return (
    <div
      ref={boxRef}
      onMouseDown={handleMouseDown}
      style={{
        position: "fixed",
        left: position.x,
        top: position.y,
        width: "230px",
        zIndex: 1050,
        background: "white",
        border: "1px solid #ccc",
        borderRadius: "8px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
        cursor: dragging ? "grabbing" : "default",
        userSelect: "none",
      }}
    >
      {/* Draggable Header */}
      <div
        className="note-header"
        style={{
          padding: "6px 10px",
          background: "#f7f7f7",
          borderBottom: "1px solid #ddd",
          borderTopLeftRadius: "8px",
          borderTopRightRadius: "8px",
          cursor: "grab",
          fontWeight: "bold",
        }}
      >
        Quick Notes
      </div>

      {/* Text Area */}
      <div style={{ padding: "10px" }}>
        <textarea
          className="form-control"
          rows={20}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Write your notes here..."
          style={{ resize: "vertical" }}
        />
      </div>
    </div>
  );
};

export default AlwaysVisibleNote;
