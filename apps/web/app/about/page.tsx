import { Shell, Icon } from "@/components/ui";
const principles = [
  {
    icon: "0ab76",
    title: "Creator Attribution Always",
    description:
      "Every recipe links to its original post, and to the creator's Instagram once verified. Results keep that credit, so the creator stays visible after you try their idea.",
  },
  {
    icon: "ebea2",
    title: "Accessible Creativity",
    description:
      "Upload a photo and try a creator's prompt right here. No copying text between tools, no setup.",
  },
  {
    icon: "8049c",
    title: "Transparent Process",
    description:
      "Every result says how it was made: live from your photo, a prepared example, or a placeholder. We never pass off a sample as your creation.",
  },
  {
    icon: "65209",
    title: "Community-Driven",
    description:
      "Prompts come from creators who tested and shared them on social media. mosAIc gathers them in one place and sends people back to talk with the people who made them.",
  },
];
export default function About() {
  return (
    <Shell about>
      <main>
        <section className="about-hero">
          <h1>About mosAIc</h1>
          <p>A place to explore, understand, and participate in Creative AI.</p>
        </section>
        <section className="mission">
          <div>
            <span className="eyebrow">The Mission</span>
            <h2>
              Make AI creativity easy to explore, without erasing creators
            </h2>
            <p>
              Creators spend hours testing and refining image prompts before
              sharing them. mosAIc collects those prompts with the
              creator&apos;s preview, lets you try them on your own photo in one
              click, and always points back to the original post and creator.
            </p>
          </div>
          <div className="lineage">
            <span>Creator&apos;s post</span>
            <Icon name="ec6b1" size={24} height={2} />
            <div>
              <span className="remix">Your creation</span>
              <span>Credit kept</span>
            </div>
          </div>
        </section>
        <section className="principles">
          <span className="eyebrow">Core Values</span>
          <h2>Our Principles</h2>
          <div className="principles-grid">
            {principles.map((p) => (
              <article key={p.title}>
                <h3>
                  <span className="principle-icon">
                    <Icon name={p.icon} size={18} />
                  </span>
                  {p.title}
                </h3>
                <p>{p.description}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="roadmap">
          <span className="eyebrow">Roadmap</span>
          <h2>What&apos;s Next</h2>
          <div className="roadmap-grid">
            {[
              {
                title: "Verified creators",
                text: "Confirm each creator and their Instagram, and show their own preview images.",
              },
              {
                title: "More recipes",
                text: "Grow beyond the first three seeds with prompts creators agree to share.",
              },
              {
                title: "Creator controls",
                text: "Let creators choose whether a prompt is public, hidden, or open to try.",
              },
              {
                title: "Mobile app",
                text: "Bring the same recipes and API to an Expo app.",
              },
            ].map((item) => (
              <article key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>
      </main>
    </Shell>
  );
}
