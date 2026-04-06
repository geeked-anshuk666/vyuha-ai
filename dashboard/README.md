# Vyuha AI Dashboard — Mission Control

This is the Next.js frontend for Vyuha AI, providing a cinematic mission control experience.

## $0 Production Deployment (Recommended)

To deploy Vyuha AI for free ($0), we recommend splitting the architecture:

### 1. Backend (Control Plane + Nodes) on Render
- **Repository**: Deploy the root directory.
- **Blueprint/Dockerfile**: Select `Dockerfile.production`.
- **Plan**: Free (Web Service).
- **Environment Variables**:
  - `GLM_API_KEY`: Your BigModel API key.
  - `VYUHA_API_KEY`: A secret key for proxy authentication.
  - `RENDER`: `true`

### 2. Frontend on Vercel
- **Subdirectory**: Configure Vercel to use the `dashboard/` folder.
- **Environment Variables**:
  - `NEXT_PUBLIC_ORCHESTRATOR_URL`: The URL provided by Render (e.g., `https://vyuha-backend.onrender.com`).

---

## Local Development

1. Install dependencies:
   ```bash
   npm install
   ```

2. Run the development server:
   ```bash
   npm run dev
   ```

3. Open [http://localhost:3000](http://localhost:3000) to see mission control.

## System Components
- `ChaosControls`: Inject failures into mock nodes.
- `AgentChat`: Interrogate the AI regarding its findings.
- `Walkthrough`: Tooltips for hackathon evaluation.
