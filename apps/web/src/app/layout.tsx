import type { Metadata } from "next"
import { Bebas_Neue, IBM_Plex_Mono, Inter } from "next/font/google"
import { NextIntlClientProvider } from "next-intl"
import { getLocale, getMessages } from "next-intl/server"
import type { ReactNode } from "react"
import "./globals.css"

const bebas = Bebas_Neue({
  variable: "--font-bebas",
  weight: "400",
  subsets: ["latin", "latin-ext"],
})

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
  subsets: ["latin", "latin-ext"],
})

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin", "latin-ext"],
})

export const metadata: Metadata = {
  title: {
    default: "Threshold",
    template: "%s — Threshold",
  },
  description:
    "Chronological social platform for underground events, artists, clubs and collectives.",
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const [locale, messages] = await Promise.all([getLocale(), getMessages()])

  return (
    <html
      lang={locale}
      className={`${bebas.variable} ${plexMono.variable} ${inter.variable} h-full`}
    >
      <body className="min-h-full bg-pitch font-sans text-raw-white">
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
