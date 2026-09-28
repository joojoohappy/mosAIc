export const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export function validateImage(
  file: { size: number; type: string } | null,
): "missing_image" | "too_large" | "unsupported_type" | null {
  if (!file || file.size === 0) return "missing_image";
  if (file.size > MAX_IMAGE_BYTES) return "too_large";
  if (!IMAGE_TYPES.some((type) => type === file.type))
    return "unsupported_type";
  return null;
}
