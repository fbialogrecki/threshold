import type { Metadata } from "next"
import { getTranslations } from "next-intl/server"
import { redirect } from "next/navigation"

import { auth } from "@/auth"

export const dynamic = "force-dynamic"

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("eventsCatalog.metadata")
  return { title: t("title"), description: t("description") }
}

export default async function EventsPage() {
  const session = await auth()
  redirect(session?.user ? "/app/events" : "/login?callbackUrl=%2Fevents")
}
