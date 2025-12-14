import React from 'react';

export default function TableCard({ columns, rows, title, helper }) {
  return (
    <div className="glass-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-white">{title}</p>
        {helper && <span className="text-xs text-white/60">{helper}</span>}
      </div>
      <div className="overflow-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-white/60">
              {columns.map((col) => (
                <th key={col.key} className="px-3 py-2 font-medium whitespace-nowrap">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-white/5">
                {columns.map((col) => (
                  <td key={col.key} className="px-3 py-3 whitespace-nowrap text-white/90">
                    {col.render ? col.render(row[col.key], row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
