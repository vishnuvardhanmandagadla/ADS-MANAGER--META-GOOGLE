import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";

const MOCK_DATA = [
  { day: "Mon", spend: 6200 },
  { day: "Tue", spend: 7400 },
  { day: "Wed", spend: 5800 },
  { day: "Thu", spend: 8900 },
  { day: "Fri", spend: 9600 },
  { day: "Sat", spend: 11200 },
  { day: "Sun", spend: 8420 },
];

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-gray-400 mb-1 font-medium">{label}</p>
      <p className="text-white">₹{payload[0].value.toLocaleString()}</p>
    </div>
  );
}

export default function SpendChart() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h3 className="text-sm font-semibold text-white">Weekly Spend</h3>
          <p className="text-xs text-gray-500 mt-0.5">Last 7 days — all clients</p>
        </div>
        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">Mock data</span>
      </div>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={MOCK_DATA} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#facc15" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#facc15" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis dataKey="day" tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fill: "#6b7280", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`} width={40} />
            <Tooltip content={<CustomTooltip />} />
            <Area type="monotone" dataKey="spend" stroke="#facc15" strokeWidth={2} fill="url(#spendGrad)" dot={false} activeDot={{ r: 4, fill: "#facc15" }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
