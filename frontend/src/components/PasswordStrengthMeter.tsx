import React from "react";
import zxcvbn from "zxcvbn";

interface PasswordStrengthMeterProps {
  password: string;
}

const PasswordStrengthMeter: React.FC<PasswordStrengthMeterProps> = ({ password }) => {
  if (!password) return null;

  const { score } = zxcvbn(password);

  const tiers = [
    { label: 'Weak password',      barColor: 'bg-red-500',    textColor: 'text-red-500'    },
    { label: 'Weak password',      barColor: 'bg-red-400',    textColor: 'text-red-400'    },
    { label: 'Medium password',    barColor: 'bg-yellow-400', textColor: 'text-yellow-600' },
    { label: 'Strong password',    barColor: 'bg-green-500',  textColor: 'text-green-600'  },
    { label: 'Strong password 💪', barColor: 'bg-green-600',  textColor: 'text-green-600'  },
  ];

  const { label, barColor, textColor } = tiers[score];
  const filledBars = score <= 1 ? 1 : score <= 3 ? 2 : 3;

  return (
    <div className="ml-1 mt-2">
      <div className="flex gap-1.5 mb-1">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className={[
              'h-2 flex-1 rounded-full border-2 border-black transition-all duration-300',
              i < filledBars ? barColor : 'bg-gray-200',
            ].join(' ')}
          />
        ))}
      </div>
      <p className={`text-xs font-bold ml-0.5 ${textColor}`}>{label}</p>
    </div>
  );
};

export default PasswordStrengthMeter;
