import { RecipeDetail } from "@/components/screens";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <RecipeDetail key={id} id={id} />;
}
