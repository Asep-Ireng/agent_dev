# AI Dev Studio 🚀

An autonomous development platform built with FastAPI and Next.js, featuring a lead designer agent and a principal developer agent.

## 🎨 Premium Theme

The Studio features a custom, premium design system:

- **Background**: Dark Navy (#25343F)
- **Accents**: Radiant Orange (#FF9B51)
- **Text**: Off-white Softness (#EAEFEF)
- **Muted**: Steel Blue (#BFC9D1)

## 🛠️ Tech Stack

- **Frontend**: Next.js 15+, Tailwind CSS, Framer Motion, Lucide Icons.
- **Backend**: FastAPI, Uvicorn, Python-dotenv.
- **Agents**: Custom implementation using Google Gemini & OpenAI.

## 🚀 Getting Started

### Prerequisites

- Node.js & npm
- Python 3.10+
- Proper API Keys (Google/OpenAI)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Asep-Ireng/agent_dev.git
   cd agent_dev
   ```
2. Configure `.env` files based on `.env.example`.
3. Run the development environment:
   ```bash
   ./start.bat
   ```

## 📂 Project Structure

- `/frontend`: Next.js web application.
- `/backend`: FastAPI service for agent orchestration.
- `agent_workflow.py`: Core logic for agentic state management.
- `app_gui.py`: Alternative GUI interface.
