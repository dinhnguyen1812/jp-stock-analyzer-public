// src/components/premarket/AlwaysVisibleNote.tsx
import React, { useState, useEffect } from "react";

const AlwaysVisibleNote: React.FC = () => {
  const [note, setNote] = useState<string>("");

  // Load note from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("quick_note");
    if (saved) {
      setNote(saved);
    }
  }, []);

  // Save note to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem("quick_note", note);
  }, [note]);

  return (
    <div
      style={{
        position: "fixed",
        right: "20px",
        top: "100px",
        width: "300px",
        zIndex: 1050,
        background: "white",
        border: "1px solid #ccc",
        borderRadius: "8px",
        padding: "12px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
      }}
    >
      <label className="form-label fw-bold">Quick Notes</label>
      <textarea
        className="form-control"
        rows={8}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Write your notes here..."
        style={{ resize: "vertical" }}
      />
    </div>
  );
};

export default AlwaysVisibleNote;
