export function splitList(input: string): string[] {
  return input
    .split(/[,;\n]/g)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function joinList(input?: string[]): string {
  return (input ?? []).join(", ")
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}
