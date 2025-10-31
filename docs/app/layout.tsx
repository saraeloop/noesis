
import type { Metadata } from 'next'
import type { ReactNode } from 'react'
import { Layout } from 'nextra-theme-docs'
import { getPageMap } from 'nextra/page-map'
import 'nextra-theme-docs/style.css'
// import './globals.css'

export const metadata: Metadata = {
  title: {
    default: 'Noēsis API',
    template: '%s – Noēsis API'
  },
  description:
    'Steer, observe, and harden agentic systems with the Noēsis control and insight API.'
}

export default async function RootLayout({
  children
}: {
  children: ReactNode
}) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body className="bg-[#050816] text-slate-100 antialiased">
        <Layout pageMap={await getPageMap()}>
          {children}
        </Layout>
      </body>
    </html>
  )
}
