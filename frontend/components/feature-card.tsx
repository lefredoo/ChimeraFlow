interface FeatureCardProps {
  title: string;
  description: string;
  icon: string;
}

export function FeatureCard({ title, description, icon }: FeatureCardProps) {
  return (
    <div className="glass-panel feature-card hover-lift">
      <div className="feature-card-icon" aria-hidden="true">
        {icon}
      </div>
      <h3 className="feature-card-title">{title}</h3>
      <p className="text-secondary">{description}</p>
    </div>
  );
}
