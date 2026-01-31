import React from 'react';
import BatchAnalysisView from './BatchAnalysisView';
import TimepointBatchAnalysisView from './TimepointBatchAnalysisView';
import SingleResultView from './SingleResultView';

export default function VisualizationFactory({ result, ...props }) {
  if (!result) return null;

  if (result.type === 'timepoint_batch_analysis') {
    return <TimepointBatchAnalysisView result={result} {...props} />;
  }

  if (result.type === 'batch_analysis' && Array.isArray(result.items)) {
    return <BatchAnalysisView result={result} {...props} />;
  }
  
  if (result.protocol_name && result.results) {
       return <TimepointBatchAnalysisView result={result} {...props} legacyStructure={true} />;
  }

  return <SingleResultView result={result} {...props} />;
}
