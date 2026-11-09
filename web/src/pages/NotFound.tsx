import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="empty">
      <h3>Page not found</h3>
      <p>That page doesn't exist.</p>
      <Link className="btn" to="/">Back to search</Link>
    </div>
  )
}
