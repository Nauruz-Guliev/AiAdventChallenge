# Advent Challenge - LLM Chat

A small web chat that sends requests to OpenCode's OpenAI-compatible API and displays responses in a responsive interface.

## Project Structure

```
advent-challenge/
├── public/           # Frontend files
│   └── index.html    # Chat interface
├── server.js         # Backend API server
├── package.json      # Project dependencies
├── .env.example      # Safe environment template
└── .gitignore       # Git ignore rules
```

## Setup & Run

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Create local configuration:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and set `OPENAI_API_KEY` locally. The real `.env` file is ignored by Git.

3. **Run the server:**
   ```bash
   npm start
   ```
   or
   ```bash
   node server.js
   ```

4. **Open your browser** and visit `http://localhost:3000`

5. **Send messages** - type in the input field and press Send, or press Enter

## Configuration

- Copy the following into `.env` and add your own key:
  ```env
  OPENAI_API_KEY=your_opencode_api_key
  OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
  ```
- The interface offers only models verified for this endpoint: Kimi K3, Qwen 3.6 Plus, and MiniMax M3.
- The API key remains on the backend and `.env` is excluded by `.gitignore`.
- The app may show a provider-generated reasoning summary when one is returned. It never exposes private hidden chain-of-thought.
- Port can be changed with the `PORT` environment variable.

## License

MIT
