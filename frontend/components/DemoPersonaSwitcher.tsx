"use client";

import { useEffect, useState } from "react";

import { DEMO_PERSONA_COOKIE, defaultDemoPersonaId, demoPersonas, personaById, personaIdFromCookie } from "@/lib/persona";

export function DemoPersonaSwitcher() {
  const [personaId, setPersonaId] = useState(defaultDemoPersonaId);

  useEffect(() => {
    setPersonaId(personaIdFromCookie(document.cookie));
  }, []);

  const persona = personaById(personaId);

  function changePersona(nextId: string) {
    document.cookie = `${DEMO_PERSONA_COOKIE}=${encodeURIComponent(nextId)}; path=/; max-age=2592000; SameSite=Lax`;
    setPersonaId(nextId);
    window.location.reload();
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-3">
      <div className="text-right">
        <p className="text-xs font-semibold text-slate-500">演示身份</p>
        <p className="text-sm font-semibold text-ink">
          {persona.label} · {persona.roleLabel}
        </p>
        <p className="hidden text-xs text-muted md:block">{persona.description}，不是生产级认证。</p>
      </div>
      <select
        value={personaId}
        onChange={(event) => changePersona(event.target.value)}
        className="focus-ring rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700"
      >
        {demoPersonas.map((item) => (
          <option key={item.id} value={item.id}>
            {item.label}
          </option>
        ))}
      </select>
    </div>
  );
}
