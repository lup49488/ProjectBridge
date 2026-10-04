import { spawn } from 'node:child_process'
import { unlink, writeFile } from 'node:fs/promises'
import { once } from 'node:events'
import { resolve } from 'node:path'

const apiUrl = process.env.PROJECTBRIDGE_API_ORIGIN ?? 'http://127.0.0.1:8019'
const projectRoot = resolve(process.cwd(), '..')
const database = process.env.DATABASE_URL?.replace(/^sqlite:\/\//, '')
let children = []
let stopping = false

async function stop(exitCode = 0) {
  if (stopping) return
  stopping = true
  for (const child of children) {
    if (child.exitCode === null && !child.killed) child.kill()
  }
  await Promise.all(children.map((child) => child.exitCode === null ? once(child, 'exit').catch(() => {}) : Promise.resolve()))
  process.exitCode = exitCode
}

process.on('SIGINT', () => { void stop(130) })
process.on('SIGTERM', () => { void stop(143) })

try {
  if (database) {
    for (const suffix of ['', '-wal', '-shm']) {
      await unlink(`${database}${suffix}`).catch((error) => {
        if (error.code !== 'ENOENT') throw error
      })
    }
  }

  const backend = spawn('python', ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'backend', '--host', '127.0.0.1', '--port', '8019'], {
    cwd: projectRoot,
    env: process.env,
    stdio: 'inherit',
    windowsHide: true,
  })
  children.push(backend)
  if (process.env.PROJECTBRIDGE_E2E_PID_FILE) await writeFile(process.env.PROJECTBRIDGE_E2E_PID_FILE, JSON.stringify([process.pid, ...children.map((child) => child.pid)]))
  backend.once('error', (error) => { console.error('Could not start the fixture API:', error); void stop(1) })
  backend.once('exit', (code) => { if (!stopping) void stop(code ?? 1) })

  const deadline = Date.now() + 25_000
  let healthy = false
  while (Date.now() < deadline && !stopping) {
    try {
      const response = await fetch(`${apiUrl}/health`)
      if (response.ok) { healthy = true; break }
    } catch { /* The backend may still be starting. */ }
    await new Promise((resolveWait) => setTimeout(resolveWait, 150))
  }
  if (!healthy) throw new Error(`Fixture API did not become ready at ${apiUrl}/health`)

  const frontend = spawn(process.execPath, [resolve('node_modules/vite/bin/vite.js'), '--host=127.0.0.1', '--port=5179', '--strictPort'], {
    cwd: process.cwd(),
    env: process.env,
    stdio: 'inherit',
    windowsHide: true,
  })
  children.push(frontend)
  if (process.env.PROJECTBRIDGE_E2E_PID_FILE) await writeFile(process.env.PROJECTBRIDGE_E2E_PID_FILE, JSON.stringify([process.pid, ...children.map((child) => child.pid)]))
  frontend.once('error', (error) => { console.error('Could not start Vite:', error); void stop(1) })
  frontend.once('exit', (code) => { if (!stopping) void stop(code ?? 1) })

  await Promise.race(children.map((child) => once(child, 'exit')))
  await stop(1)
} catch (error) {
  console.error(error)
  await stop(1)
}
