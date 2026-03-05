// server/src/claude-session.ts
import { spawn } from 'child_process';

export interface ClaudeSessionConfig {
  workspaceDir: string;
  permissionMode: string;
  timeoutMs?: number;  // per-turn timeout (default: 180000ms)
}

interface ClaudeJsonResponse {
  type: string;
  session_id: string;
  result: string;
  cost_usd?: number;
  duration_ms?: number;
  duration_api_ms?: number;
  is_error?: boolean;
  num_turns?: number;
}

export class ClaudeSessionManager {
  private sessionId: string | null = null;
  private config: ClaudeSessionConfig;
  private disposed = false;

  constructor(config: ClaudeSessionConfig) {
    this.config = config;
  }

  /**
   * Send a message to Claude CLI and get the response text.
   * First call creates a new session; subsequent calls use --resume.
   */
  async sendMessage(text: string): Promise<string> {
    if (this.disposed) {
      throw new Error('ClaudeSessionManager has been disposed');
    }

    const timeoutMs = this.config.timeoutMs ?? 180000;
    const args = ['--print', '--output-format', 'json', '--verbose'];

    if (this.config.permissionMode) {
      args.push('--permission-mode', this.config.permissionMode);
    }

    if (this.sessionId) {
      args.push('--resume', this.sessionId);
    }

    console.error(`[claude-session] Sending message (session=${this.sessionId || 'new'}): ${text.substring(0, 80)}...`);

    const proc = spawn('claude', args, {
      cwd: this.config.workspaceDir,
      stdio: ['pipe', 'pipe', 'pipe'],
      env: { ...process.env },
    });

    return new Promise<string>((resolve, reject) => {
      let stdout = '';
      let stderr = '';

      const timer = setTimeout(() => {
        proc.kill('SIGTERM');
        reject(new Error(`Claude CLI timeout after ${timeoutMs}ms`));
      }, timeoutMs);

      proc.stdout!.on('data', (chunk: Buffer) => {
        stdout += chunk.toString();
      });

      proc.stderr!.on('data', (chunk: Buffer) => {
        stderr += chunk.toString();
      });

      proc.on('close', (code) => {
        clearTimeout(timer);

        if (stderr) {
          console.error(`[claude-session] stderr: ${stderr.substring(0, 200)}`);
        }

        if (code !== 0 && code !== null) {
          reject(new Error(`Claude CLI exited with code ${code}: ${stderr.substring(0, 200)}`));
          return;
        }

        try {
          const result = JSON.parse(stdout) as ClaudeJsonResponse;

          if (!this.sessionId && result.session_id) {
            this.sessionId = result.session_id;
            console.error(`[claude-session] New session: ${this.sessionId}`);
          }

          if (result.is_error) {
            reject(new Error(`Claude error: ${result.result}`));
            return;
          }

          resolve(result.result);
        } catch (parseError) {
          if (stdout.trim()) {
            resolve(stdout.trim());
          } else {
            reject(new Error(`Failed to parse Claude response: ${stdout.substring(0, 200)}`));
          }
        }
      });

      proc.on('error', (err) => {
        clearTimeout(timer);
        reject(new Error(`Failed to spawn claude CLI: ${err.message}`));
      });

      proc.stdin!.write(text);
      proc.stdin!.end();
    });
  }

  dispose(): void {
    this.disposed = true;
    this.sessionId = null;
  }

  getSessionId(): string | null {
    return this.sessionId;
  }

  isDisposed(): boolean {
    return this.disposed;
  }
}
