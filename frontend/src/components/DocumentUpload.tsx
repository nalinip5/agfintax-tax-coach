import { useRef, useState } from 'react'
import { api } from '../lib/api'

const USER_ID = 'demo-user'

type UploadResult = {
  title: string
  redacted_categories: string[]
  redaction_count: number
  note: string
}

export default function DocumentUpload() {
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    setUploading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.uploadDocumentFile(USER_ID, file.name, file)
      setResult(res)
    } catch (e) {
      setError('Upload failed — the file may be an unsupported type, or the extraction service is temporarily unavailable.')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  return (
    <div className="rounded-xl border border-ledger-200 bg-white p-4">
      <h2 className="font-serif text-lg text-ledger-900">Upload a document</h2>
      <p className="mt-1 text-xs text-ledger-600">
        W-2, 1099, or other tax documents. Text is extracted and any personal identifiers are
        automatically redacted before storage.
      </p>

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg,.tiff"
        className="mt-3 block w-full text-xs text-ledger-700 file:mr-3 file:rounded-md file:border-0 file:bg-ledger-100 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-ledger-700 hover:file:bg-ledger-200"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
        disabled={uploading}
      />

      {uploading && <p className="mt-2 text-xs text-ledger-500">Extracting and scrubbing…</p>}

      {error && <p className="mt-2 text-xs text-clay-600">{error}</p>}

      {result && (
        <div className="mt-3 rounded-lg bg-ledger-50 p-3 text-xs text-ledger-700">
          <p className="font-medium text-ledger-900">"{result.title}" processed.</p>
          {result.redaction_count > 0 ? (
            <p className="mt-1">
              Redacted {result.redaction_count} sensitive item{result.redaction_count === 1 ? '' : 's'}{' '}
              ({result.redacted_categories.join(', ')}) before storage.
            </p>
          ) : (
            <p className="mt-1">No personal identifiers were detected.</p>
          )}
          <p className="mt-1 text-ledger-500">{result.note}</p>
        </div>
      )}
    </div>
  )
}
