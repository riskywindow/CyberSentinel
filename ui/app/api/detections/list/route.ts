import { NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

export async function GET() {
  try {
    const dir = path.join(process.cwd(), '..', 'detections', 'sigma', 'rules')
    const files = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.yml') || f.endsWith('.yaml')) : []
    const items = files.map(f => {
      const p = path.join(dir, f)
      const text = fs.readFileSync(p, 'utf8')
      const title = (text.match(/^title:\s*(.*)$/m)?.[1] || f).trim()
      return { file: f, title }
    })
    return NextResponse.json({ rules: items })
  } catch (e) {
    return NextResponse.json({ rules: [] }, { status: 200 })
  }
}