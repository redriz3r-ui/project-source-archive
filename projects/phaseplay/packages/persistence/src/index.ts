import type { Session } from "@phaseplay/domain";

export interface SessionRepository {
  get(id: string): Promise<Session | null>;
  save(session: Session): Promise<Session>;
  list(): Promise<Session[]>;
}

export class InMemorySessionRepository implements SessionRepository {
  private readonly sessions = new Map<string, Session>();
  async get(id: string) { return this.sessions.get(id) ?? null; }
  async save(session: Session) { this.sessions.set(session.id, structuredClone(session)); return session; }
  async list() { return [...this.sessions.values()].map((session) => structuredClone(session)); }
}
