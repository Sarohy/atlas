const SIGN_IN_HERO_ASSET = '/atlas.svg';

export function HeroPanel() {
  return (
    <div className="atlas-auth-desktop-hero">
      <img
        alt="ATLAS market globe"
        className="atlas-auth-desktop-hero-image"
        src={SIGN_IN_HERO_ASSET}
      />
    </div>
  );
}
