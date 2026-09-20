// StudentsPage behavior: renders the paginated envelope, searches, and shows
// API errors instead of failing silently.
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import StudentsPage from '../pages/StudentsPage'
import * as apiModule from '../api'

vi.mock('../api', () => ({
  api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

// StudentsPage is admin-only in the router but renders standalone here.
const PAGE = { items: [
  { student_id: 1, student_code: 'STU-0001', first_name: 'Maya', last_name: 'Chen', email: 'maya@x.edu', courses: 'BIO101', avg_grade: 88.5 },
  { student_id: 2, student_code: 'STU-0002', first_name: 'Liam', last_name: 'Okafor', email: 'liam@x.edu', courses: null, avg_grade: null },
], page: 2, page_size: 20, total: 41, total_pages: 3 }

beforeEach(() => {
  vi.clearAllMocks()
  apiModule.api.get.mockImplementation((path) => {
    if (path.startsWith('/students?')) return Promise.resolve(PAGE)
    return Promise.resolve([])
  })
  window.confirm = vi.fn(() => false)
})

describe('StudentsPage', () => {
  it('renders student rows from the paginated envelope', async () => {
    render(<StudentsPage />)
    expect(await screen.findByText('Maya Chen')).toBeInTheDocument()
    expect(screen.getByText('Liam Okafor')).toBeInTheDocument()
    expect(screen.getByText('STU-0001')).toBeInTheDocument()
    expect(screen.getByText('88.50')).toBeInTheDocument()
  })

  it('shows pagination controls when there are multiple pages', async () => {
    render(<StudentsPage />)
    await screen.findByText('Maya Chen')
    expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument()
    expect(screen.getByText(/41 records/)).toBeInTheDocument()
  })

  it('re-fetches with the search term when the user types', async () => {
    render(<StudentsPage />)
    await screen.findByText('Maya Chen')
    const user = userEvent.setup()
    await user.type(screen.getByRole('searchbox'), 'maya')
    await waitFor(() => {
      const last = apiModule.api.get.mock.calls.at(-1)[0]
      expect(last).toContain('search=maya')
      expect(last).toContain('page=1')
    })
  })

  it('displays an API error message instead of rows', async () => {
    apiModule.api.get.mockRejectedValue(new Error('Database unavailable'))
    render(<StudentsPage />)
    expect(await screen.findByText('Database unavailable')).toBeInTheDocument()
    expect(screen.queryByText('Maya Chen')).not.toBeInTheDocument()
  })

  it('shows the empty state when no students match', async () => {
    apiModule.api.get.mockResolvedValue({ items: [], page: 1, page_size: 20, total: 0, total_pages: 1 })
    render(<StudentsPage />)
    expect(await screen.findByText('No students match.')).toBeInTheDocument()
  })
})
