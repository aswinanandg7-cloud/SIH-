# MandiMitra — Agricultural Procurement Portal

Mobile-first React + TypeScript web application powered by Vite.

## Recent Architecture Updates
- **Removal of Backend and Supabase**: The application has been restructured to minimize dependencies. Legacy FastAPI backend and Supabase requirements have been removed or abstracted.
- **QR Scanner**: Implemented a fully functional native QR scanner (`html5-qrcode`) for quick token verification directly in the browser, featuring automatic token prefix filtering.
- **UI Adjustments**: Removed excessive decorative emojis across the frontend for a cleaner, more professional interface.

## Software Requirements

- Node.js: `v18.0.0+` or `v20.0.0+` (LTS recommended)
- npm: `v9.0.0+`

## How to Start

1. Install Dependencies:
   ```bash
   npm install
   ```

2. Run Development Server:
   ```bash
   npm run dev
   ```
   *Access the app at `http://localhost:5173`.*

3. Available Scripts:
   - `npm run dev`: Starts local development server
   - `npm run build`: Compiles TypeScript and builds production distribution artifacts into `dist/`
   - `npm run preview`: Previews locally built production bundle
