'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';

const url = '/api/v1/vacancy-requests';
const labels: Record<string, string> = {
  queued: 'Na fila',
  neon: 'Preparando com Gemini Neon',
  argon: 'Preparando com Gemini Argon (quota do Neon)',
  failed: 'Falha na geração ou validação. Revise a vaga e tente novamente.',
  interrupted: 'Pedido interrompido. Envie novamente.',
  done: 'Pronto para revisão',
};
type Item = { id: string; status: string; resume: string | null };
export function VacancyDraft() {
  const [items, setItems] = useState<Item[] | null>(null),
    [text, setText] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const key = useRef('');
  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const r = await fetch(url, { cache: 'no-store' });
        if (r.ok) {
          const data = await r.json();
          if (alive) setItems(data);
        }
      } catch {
        /* Next poll retries. */
      }
    }
    void load();
    const timer = setInterval(load, 5000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  if (!items) return null;
  return (
    <section className="col-span-full border-2 border-ink p-5 space-y-3">
      <h2 className="text-xl font-bold">Currículo e carta para uma vaga</h2>
      <p>
        Usa o currículo master padrão. Os documentos ficam aqui para revisão; nenhuma candidatura é
        enviada.
      </p>
      <form
        className="space-y-2"
        onSubmit={async (e) => {
          e.preventDefault();
          if (busy) return;
          setBusy(true);
          setError('');
          key.current ||= crypto.randomUUID();
          try {
            const r = await fetch(url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', 'X-Resume-Workflow': '1' },
              body: JSON.stringify({ id: key.current, description: text }),
            });
            if (!r.ok)
              throw new Error(
                r.status === 409
                  ? 'Selecione um currículo master estruturado primeiro.'
                  : r.status === 429
                    ? 'Já há pedidos na fila. Aguarde.'
                    : 'Não foi possível enviar. Tente novamente.'
              );
            const { id } = await r.json();
            setItems((prev) => [
              { id, status: 'queued', resume: null },
              ...(prev ?? []).filter((x) => x.id !== id),
            ]);
            setText('');
            key.current = '';
          } catch (err) {
            setError(err instanceof Error ? err.message : 'Falha ao enviar.');
          } finally {
            setBusy(false);
          }
        }}
      >
        <label htmlFor="vacancy-description">Descrição da vaga</label>
        <textarea
          id="vacancy-description"
          required
          minLength={30}
          maxLength={24000}
          className="block w-full border border-ink p-2"
          rows={4}
          value={text}
          onChange={(e) => {
            key.current = '';
            setText(e.target.value);
          }}
        />
        <button
          className="border-2 border-ink px-4 py-2 font-bold"
          disabled={busy || text.trim().length < 30}
        >
          {busy ? 'Enviando…' : 'Gerar currículo e carta'}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      <ul aria-live="polite">
        {items.map((x) => (
          <li key={x.id}>
            {labels[x.status] ?? x.status}{' '}
            {x.resume && (
              <Link className="underline" href={`/resumes/${x.resume}`}>
                Abrir currículo e carta
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
