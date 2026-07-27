import type { Metadata, Viewport } from "next"
import { Archivo, IBM_Plex_Mono } from "next/font/google"
import { NextIntlClientProvider } from "next-intl"
import { getLocale, getMessages } from "next-intl/server"
import type { ReactNode } from "react"
import "./globals.css"

// One grotesque covers titles and body: Archivo has the weight axis Bebas
// lacked, and unlike Bebas it has lowercase, which usernames need.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin", "latin-ext"],
})

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  weight: ["400", "500", "600"],
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

export const viewport: Viewport = { themeColor: "#030303" }

export default async function RootLayout({ children }: { children: ReactNode }) {
  const [locale, messages] = await Promise.all([getLocale(), getMessages()])

  return (
    <html lang={locale} className={`${archivo.variable} ${plexMono.variable} h-full`}>
      <body className="min-h-full bg-pitch font-sans text-raw-white">
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
