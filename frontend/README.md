# Q&A System Frontend

React + TypeScript frontend application for the Q&A System, built with Vite, Tailwind CSS, and React Context API.

## Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- FastAPI backend running on `http://localhost:8000` (or configure `VITE_API_BASE_URL`)

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   # or
   yarn install
   # or
   pnpm install
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env.local
   ```
   Edit `.env.local` to set your backend URL if different from default.

3. **Start development server**:
   ```bash
   npm run dev
   # or
   yarn dev
   # or
   pnpm dev
   ```

   The app will be available at `http://localhost:5173`

## Available Scripts

- `npm run dev` - Start Vite development server with hot module replacement
- `npm run build` - Build for production (outputs to `dist/`)
- `npm run preview` - Preview production build locally
- `npm run lint` - Run ESLint

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client and types
│   ├── components/       # React components
│   ├── contexts/         # React Context providers
│   ├── hooks/            # Custom React hooks
│   ├── App.tsx           # Root component
│   ├── main.tsx          # Entry point
│   └── index.css         # Global styles
├── public/               # Static assets
├── index.html            # HTML template
├── vite.config.ts        # Vite configuration
├── tailwind.config.js    # Tailwind CSS configuration
└── tsconfig.json         # TypeScript configuration
```

## Features

- **Session Management**: Create and load Q&A sessions
- **User Roles**: Junior (view-only) and Senior (can edit answers)
- **Question Processing**: Enter multiple questions and generate answers
- **Q&A Blocks**: Editable answer blocks with citations
- **Responsive Design**: Mobile-friendly layout with collapsible sidebar

## Development

### Adding New Components

1. Create component file in `src/components/`
2. Export from component file
3. Import and use in parent components

### API Integration

All API calls are handled through `src/api/client.ts`. The client automatically handles:
- Error handling and transformation
- Base URL configuration
- Request/response types

### State Management

State is managed using React Context API:
- `SessionContext`: Manages current session and user role
- `QABlocksContext`: Manages Q&A pairs and processing state

## Building for Production

```bash
npm run build
```

The production build will be in the `dist/` directory. You can preview it with:

```bash
npm run preview
```

## Backend Integration

The frontend expects the FastAPI backend (Phase 1.8) to be running and providing these endpoints:

- `POST /api/sessions` - Create session
- `GET /api/sessions` - List sessions
- `GET /api/sessions/{id}` - Get session
- `POST /api/sessions/{id}/questions` - Process questions
- `GET /api/sessions/{id}/qa-pairs` - Get Q&A pairs
- `PUT /api/qa-pairs/{id}` - Update answer
- `PUT /api/sessions/{id}/outcome` - Mark outcome

## Troubleshooting

### CORS Errors

Make sure the FastAPI backend has CORS configured to allow requests from `http://localhost:5173`.

### API Connection Issues

1. Verify backend is running on the configured port
2. Check `VITE_API_BASE_URL` in `.env.local`
3. Check browser console for detailed error messages

### Build Issues

1. Clear `node_modules` and reinstall: `rm -rf node_modules && npm install`
2. Clear Vite cache: `rm -rf node_modules/.vite`
3. Check TypeScript errors: `npx tsc --noEmit`

