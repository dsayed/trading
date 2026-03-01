import { useState, type KeyboardEvent } from 'react';

interface Props {
  symbols: string[];
  onChange: (symbols: string[]) => void;
}

export default function SymbolInput({ symbols, onChange }: Props) {
  const [input, setInput] = useState('');

  function addSymbol() {
    const sym = input.trim().toUpperCase();
    if (sym && /^[A-Z]{1,5}$/.test(sym) && !symbols.includes(sym)) {
      onChange([...symbols, sym]);
    }
    setInput('');
  }

  function removeSymbol(sym: string) {
    onChange(symbols.filter((s) => s !== sym));
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addSymbol();
    }
    if (e.key === 'Backspace' && input === '' && symbols.length > 0) {
      removeSymbol(symbols[symbols.length - 1]);
    }
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1.5">
        {symbols.map((sym) => (
          <span
            key={sym}
            className="inline-flex items-center gap-1 rounded-md bg-zinc-800 px-2.5 py-1 font-mono text-sm text-zinc-200"
          >
            {sym}
            <button
              onClick={() => removeSymbol(sym)}
              className="ml-0.5 text-zinc-500 transition-colors hover:text-red-400"
            >
              &times;
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value.toUpperCase())}
          onKeyDown={handleKeyDown}
          placeholder="Add symbol (e.g. AAPL)"
          className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          maxLength={5}
        />
        <button
          onClick={addSymbol}
          className="rounded-md bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-300 transition-colors hover:bg-zinc-700"
        >
          Add
        </button>
      </div>
    </div>
  );
}
