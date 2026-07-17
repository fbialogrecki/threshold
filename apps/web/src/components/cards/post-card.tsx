import {
  CalendarBlank,
  MapPin,
  UsersThree,
} from "@phosphor-icons/react/ssr"
import { getLocale, getTranslations } from "next-intl/server"
import Link from "next/link"

import { CommentsSection } from "@/components/social/comments-section"
import { EmojiReactionBar } from "@/components/social/emoji-reaction-bar"
import { PostBody } from "@/components/social/post-body"
import { VoteButtons } from "@/components/social/vote-buttons"
import { Avatar } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { MonoLabel } from "@/components/ui/mono-label"
import { TagRow } from "@/components/ui/tag"
import { cityLabel } from "@/lib/cities"
import { formatRelative } from "@/lib/format"
import { mediaDerivativeUrl } from "@/lib/media/urls"
import { profileHref } from "@/lib/profile-href"
import { safeInternalHref } from "@/lib/safe-href"
import type { Comment, ThresholdEvent, Post } from "@/lib/types"

function eventDate(iso: string, locale: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ""
  return new Intl.DateTimeFormat(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }).format(date)
}

function FeedEventWidget({
  event,
  locale,
  labels,
}: {
  event: ThresholdEvent
  locale: string
  labels: {
    lineup: string
    locationTba: string
    secretLocation: string
    viewEvent: string
  }
}) {
  const posterUrl = event.poster_media_asset_id
    ? mediaDerivativeUrl(event.poster_media_asset_id, "post_1280")
    : null
  const city = event.city ? cityLabel(event.city, locale) : null
  const location = event.location_mode === "secret_location"
    ? labels.secretLocation
    : event.location_mode === "tba"
      ? labels.locationTba
      : [event.venue_name, event.address, city].filter(Boolean).join(" · ")

  return (
    <section className="mt-4 overflow-hidden border border-border-gray bg-pitch">
      <div className="grid sm:grid-cols-[minmax(0,2fr)_minmax(15rem,1fr)]">
        {posterUrl ? (
          <Link href={`/events/${event.slug}`} className="block min-h-64 bg-raised">
            <img
              src={posterUrl}
              alt={event.title}
              width={820}
              height={1025}
              loading="lazy"
              decoding="async"
              className="aspect-[4/5] h-full max-h-[34rem] w-full object-cover"
            />
          </Link>
        ) : (
          <Link
            href={`/events/${event.slug}`}
            className="flex min-h-64 items-end bg-raised p-5"
          >
            <span className="font-display text-5xl leading-[0.9] tracking-wide text-raw-white">
              {event.title}
            </span>
          </Link>
        )}
        <div className="flex flex-col justify-between border-t border-border-gray p-4 sm:border-l sm:border-t-0">
          <div>
            {posterUrl ? (
              <Link
                href={`/events/${event.slug}`}
                className="font-display text-3xl leading-none tracking-wide text-raw-white hover:text-acid"
              >
                {event.title}
              </Link>
            ) : null}
            <dl className="mt-4 grid gap-3 text-sm text-dim-white">
              <div className="flex gap-2">
                <CalendarBlank size={18} className="mt-0.5 shrink-0 text-violet" aria-hidden />
                <dd>{eventDate(event.starts_at, locale)}</dd>
              </div>
              <div className="flex gap-2">
                <MapPin size={18} className="mt-0.5 shrink-0 text-violet" aria-hidden />
                <dd>{location || labels.locationTba}</dd>
              </div>
              {event.lineup.length > 0 ? (
                <div className="flex gap-2">
                  <UsersThree size={18} className="mt-0.5 shrink-0 text-violet" aria-hidden />
                  <dd>
                    <span className="sr-only">{labels.lineup}: </span>
                    {event.lineup.map((item, index) => {
                      const name = typeof item === "string" ? item : item.display_name ?? item.name
                      const href = typeof item === "string" ? null : safeInternalHref(item.target_url)
                      return (
                        <span key={`${name}-${index}`}>
                          {index > 0 ? " / " : null}
                          {href ? <Link href={href} className="text-cyan hover:underline">{name}</Link> : name}
                        </span>
                      )
                    })}
                  </dd>
                </div>
              ) : null}
            </dl>
          </div>
          <Link
            href={`/events/${event.slug}`}
            className="mt-5 border-t border-border-gray pt-3 font-mono text-[11px] uppercase tracking-label text-acid hover:text-raw-white"
          >
            {labels.viewEvent} →
          </Link>
        </div>
      </div>
    </section>
  )
}

export async function PostCard({
  post,
  initialComments,
  commentsDefaultOpen = false,
  redirectHomeOnDelete = false,
}: {
  post: Post
  initialComments?: Comment[]
  commentsDefaultOpen?: boolean
  redirectHomeOnDelete?: boolean
}) {
  const [locale, t] = await Promise.all([getLocale(), getTranslations("post")])
  const href = profileHref(post.author)

  return (
    <Card as="article">
      <div className="flex gap-3 px-4 py-4">
        <Link href={href}>
          <Avatar name={post.author.displayName} imageUrl={post.author.avatarUrl} />
        </Link>
        <div className="min-w-0 flex-1">
          <PostBody
            postId={post.id}
            body={post.body}
            mentions={post.mentions}
            editedAtIso={post.editedAtIso}
            viewerIsAuthor={post.viewerIsAuthor && !post.systemOwned}
            redirectHomeOnDelete={redirectHomeOnDelete}
            header={(
              <div className="min-w-0">
                <Link
                  href={href}
                  className="block truncate font-display text-xl tracking-wide text-raw-white hover:text-acid"
                >
                  {post.author.displayName}
                </Link>
                <p className="truncate font-mono text-[11px] text-muted">@{post.author.handle}</p>
              </div>
            )}
            age={(
              <Link href={`/posts/${post.id}`} className="hover:text-acid">
                <MonoLabel size="xs">{formatRelative(post.createdAtIso, locale)}</MonoLabel>
              </Link>
            )}
          />

          {post.media.length > 0 ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {post.media.map((item) => (
                <img
                  key={item.assetId}
                  src={item.url}
                  alt={t("attachmentAlt")}
                  width={820}
                  height={615}
                  loading="lazy"
                  decoding="async"
                  className="aspect-[4/3] max-h-[420px] w-full border border-border-gray object-cover"
                />
              ))}
            </div>
          ) : null}

          {post.linkedEvent ? (
            <FeedEventWidget
              event={post.linkedEvent}
              locale={locale}
              labels={{
                lineup: t("lineup"),
                locationTba: t("locationTba"),
                secretLocation: t("secretLocation"),
                viewEvent: t("viewEvent"),
              }}
            />
          ) : null}

          <TagRow className="mt-3" tags={post.tags} />
          <CommentsSection
            postId={post.id}
            commentCount={post.commentCount}
            initialComments={initialComments}
            defaultOpen={commentsDefaultOpen}
            reactions={<EmojiReactionBar postId={post.id} reactions={post.emojiReactions} />}
            votes={(
              <VoteButtons
                targetType="post"
                targetId={post.id}
                upCount={post.upCount}
                downCount={post.downCount}
                viewerVote={post.viewerVote}
              />
            )}
          />
        </div>
      </div>
    </Card>
  )
}
