import React from 'react';
import ProtocolTemplateSelector from './ProtocolTemplateSelector';

export default function TemplatePanel(props) {
  return (
    <div className="bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] overflow-hidden">
      <ProtocolTemplateSelector {...props} />
    </div>
  );
}

