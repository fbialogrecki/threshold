import { EventEditorPage } from "@/components/event/event-editor-page"
export const dynamic = "force-dynamic"
export default async function EditEventPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <EventEditorPage slug={slug} />
}
