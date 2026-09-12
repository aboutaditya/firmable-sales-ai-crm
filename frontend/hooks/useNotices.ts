"use client";

import { useState } from "react";

export function useNotices() {
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  return { error, notice, setError, setNotice, clear: () => { setError(""); setNotice(""); } };
}