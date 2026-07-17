export type ProfileFormValues = {
  displayName: string
  username: string
  bio: string
  city: string
  avatarMediaAssetId: string
}

export function buildProfilePayload(
  values: ProfileFormValues,
  savedAvatarMediaAssetId: string,
) {
  const avatar = values.avatarMediaAssetId.trim()
  return {
    display_name: values.displayName.trim(),
    username: values.username.trim(),
    bio: values.bio.trim(),
    city: values.city.trim(),
    ...(avatar && avatar !== savedAvatarMediaAssetId ? { avatar_media_asset_id: avatar } : {}),
  }
}
