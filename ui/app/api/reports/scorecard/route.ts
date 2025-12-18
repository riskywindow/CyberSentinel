import { NextResponse } from 'next/server'
import fs from 'node:fs'
import path from 'node:path'

export async function GET() {
  const p = path.join(process.cwd(), '..', 'eval', 'scorecard.json')
  if (!fs.existsSync(p)) return NextResponse.json({ run_started: null, scenarios: [] })
  const text = fs.readFileSync(p, 'utf8')
  return NextResponse.json(JSON.parse(text))
}