import { readFile, unlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export default async function globalTeardown() {
  const pidFile = join(tmpdir(), 'projectbridge-e2e-processes.json')
  try {
    const [managerPid] = JSON.parse(await readFile(pidFile, 'utf8')) as number[]
    process.kill(managerPid, 'SIGTERM')
  } catch (error) {
    if (!['ENOENT', 'ESRCH'].includes((error as NodeJS.ErrnoException).code ?? '')) throw error
  } finally {
    await unlink(pidFile).catch(() => {})
  }
}
