import { Check, Copy, Terminal } from "lucide-react"
import { useState } from "react"

type CommandPanelProps = {
  command: string
}

export default function CommandPanel({ command }: CommandPanelProps) {
  const [copied, setCopied] = useState(false)

  async function copyCommand() {
    await navigator.clipboard.writeText(command)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <article className="panel-section command-panel">
      <div className="panel-title-row">
        <h2>
          <Terminal size={18} />
          Reproducible command
        </h2>
        <button className="mini-button" type="button" onClick={copyCommand}>
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? "Copied" : "Copy command"}
        </button>
      </div>
      <code>{command}</code>
    </article>
  )
}
