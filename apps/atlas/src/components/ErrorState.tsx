import { AlertTriangle } from "lucide-react"

type ErrorStateProps = {
  message: string
}

export default function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={18} />
      <span>{message}</span>
    </div>
  )
}
