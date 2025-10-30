import React from 'react'
import type { DocsThemeConfig } from 'nextra-theme-docs'

const themeConfig: DocsThemeConfig = {
  logo: (
    <div className="flex items-center gap-2 font-semibold leading-none text-slate-100">
      <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-[#7c3aed] via-[#6366f1] to-[#22d3ee] text-base text-white shadow-[0_0_18px_rgba(99,102,241,0.45)]">
        Ν
      </span>
      <span className="hidden text-sm tracking-tight sm:inline">Noēsis API</span>
    </div>
  ),
  logoLink: '/',
  project: {
    link: 'https://github.com/saraeloop/noesis'
  },
  docsRepositoryBase: 'https://github.com/saraeloop/noesis/tree/main/docs',
  faviconGlyph: '𝓝',
  toc: {
    title: 'On this page',
    extraContent: null
  },
  search: {
    placeholder: 'Search the docs...'
  },
  sidebar: {
    defaultMenuCollapseLevel: 0,
    toggleButton: true
  },
  navbar: {
    extraContent: (
      <a
        className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-sm font-medium text-white transition hover:border-white/35 hover:bg-white/10"
        href="https://github.com/saraeloop/noesis"
        target="_blank"
        rel="noreferrer"
      >
        <svg
          aria-hidden
          focusable="false"
          width="16"
          height="16"
          stroke="currentColor"
          strokeWidth="1.5"
          fill="none"
          viewBox="0 0 24 24"
        >
          <path
            d="m12 3 1.89 5.82H20l-4.45 3.23 1.7 5.95L12 15.73l-5.25 2.27 1.7-5.95L4 8.82h6.11L12 3Z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        Star on GitHub
      </a>
    )
  },
  editLink: {
    text: 'Edit this page on GitHub →'
  },
  feedback: {
    content: 'Question? Give us feedback →'
  },
  footer: {
    text: () => (
      <span className="text-sm text-slate-300">
        MIT {new Date().getFullYear()} © Noēsis. Built for resilient agents.
      </span>
    )
  },
  gitTimestamp: null,
  useNextSeoProps() {
    return {
      titleTemplate: '%s – Noēsis API',
      defaultTitle: 'Noēsis API'
    }
  },
  primaryHue: {
    light: 262,
    dark: 262
  },
  primarySaturation: {
    light: 82,
    dark: 72
  },
  head: () => (
    <>
      <meta name="theme-color" content="#050816" />
      <meta
        name="description"
        content="Steer, observe, and harden agentic systems through the Noēsis API."
      />
      <meta property="og:title" content="Noēsis API" />
      <meta
        property="og:description"
        content="Guides, reference material, and examples for integrating the Noēsis control layer."
      />
    </>
  )
}

export default themeConfig
