import { getTranslations } from "next-intl/server"

import { SkeletonFeed } from "@/components/ui/skeleton"

export default async function AppLoading() {
  const t = await getTranslations("loading")
  return <SkeletonFeed label={t("feed")} ariaLabel={t("aria")} />
}
