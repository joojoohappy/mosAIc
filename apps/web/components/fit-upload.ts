// Some hosts cap request bodies (Vercel functions: 4.5MB), below the backend's
// 8MB limit. Large photos are re-encoded in the browser so they still fit.
// Small photos are sent untouched.
export const UPLOAD_TARGET_BYTES = 4 * 1024 * 1024;
const MAX_SIDE = 2048;

export async function fitForUpload(file: File): Promise<File> {
  if (
    file.size <= UPLOAD_TARGET_BYTES ||
    typeof createImageBitmap !== "function"
  )
    return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas
      .getContext("2d")
      ?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    for (const quality of [0.9, 0.8, 0.7]) {
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", quality),
      );
      if (blob && blob.size <= UPLOAD_TARGET_BYTES)
        return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", {
          type: "image/jpeg",
        });
    }
  } catch {
    // Fall through: send the original and let the server decide.
  }
  return file;
}
