"use client";

import { useEffect, useState } from "react";

import { formatDate, isSameLocalDay } from "@/lib/format";

export function LocalDate({ value }: { value: string | null | undefined }) {
  const [text, setText] = useState("-");

  useEffect(() => {
    setText(formatDate(value));
  }, [value]);

  return <>{text}</>;
}

export function LocalTodayCount({ values }: { values: string[] }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    setCount(values.filter((value) => isSameLocalDay(value)).length);
  }, [values]);

  return <>{count}</>;
}
