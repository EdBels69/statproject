import re
import uuid

class ProtocolAgent:
    """
    Translates natural language descriptions into a React Flow graph structure.
    Simulates 'AI' reasoning with robust heuristics for the MVP.
    """
    
    def parse_instruction(self, text: str) -> dict:
        """
        Parses chat input like "Compare 3 groups (A, B, C) over 4 visits (T0, T1, T2, T3)"
        Returns a React Flow JSON { nodes: [], edges: [] }
        """
        text = text.lower()
        nodes = []
        edges = []
        
        # 1. Detect Timepoints (Visits)
        # Regex for "X visits", "over X months", or explicit definition
        visits = ["Baseline"] # Default start
        
        # Heuristic: "3 visits", "4 timepoints"
        count_match = re.search(r'(\d+)\s*(?:visit|timepoint|month|week)', text)
        if count_match:
            count = int(count_match.group(1))
            # Generate T1...TN
            visits = [f"Visit {i+1}" for i in range(count)]
            if "baseline" in text or "start" in text:
                visits.insert(0, "Baseline")
        
        # Heuristic: "T0, T1, T2"
        explicit_match = re.search(r'\((t\d+.*)\)', text)
        if explicit_match:
            # Extract comma separated
            parts = [p.strip() for p in explicit_match.group(1).split(',')]
            if len(parts) > 1:
                visits = parts

        # 2. Detect Groups
        groups = ["All Patients"]
        group_match = re.search(r'(\d+)\s*groups?', text)
        if group_match:
            # If explicit names given? "Groups A, B"
            if "groups" in text and "(" in text:
                 # Try to find group names inside parens near 'groups'
                 pass # Too complex for simple regex, stick to generic
            else:
                 groups = [f"Group {chr(65+i)}" for i in range(int(group_match.group(1)))]

        # 3. Detect Measures
        # "Measure Hb and Weight"
        measures = []
        if "measure" in text or "track" in text:
            # Simple keyword extraction (mocking NLP)
            keywords = ["hb", "weight", "bmi", "age", "pressure", "score"]
            for k in keywords:
                if k in text:
                    measures.append(k.capitalize())
        
        # --- Build Graph ---
        x_pos = 50
        y_pos = 100
        prev_node_id = None
        
        # Create Source
        source_id = "node_src"
        nodes.append({
            "id": source_id,
            "type": "timepoint", # reusing timepoint for source for now, or 'source'
            "position": {"x": x_pos, "y": y_pos},
            "data": {
                "label": "Study Population", 
                "isStart": True,
                "measures": ["Demographics"]
            }
        })
        prev_node_id = source_id
        x_pos += 250
        
        # If groups detected, split? 
        # For timeline view, we often show visits linearly. 
        # Visual Constructor vs Flowchart: 
        # Let's do Linear Timepoints for the "Experiment Builder"
        
        for i, v in enumerate(visits):
            # Create Node
            node_id = f"node_t{i}"
            nodes.append({
                "id": node_id,
                "type": "timepoint",
                "position": {"x": x_pos, "y": y_pos},
                "data": {
                    "label": v,
                    "measures": measures if len(measures) > 0 else ["Key Outcome"],
                    "groups": groups
                }
            })
            
            # Link
            edges.append({
                "id": f"edge_{prev_node_id}_{node_id}",
                "source": prev_node_id,
                "target": node_id,
                "animated": True
            })
            
            prev_node_id = node_id
            x_pos += 250
            
        return {"nodes": nodes, "edges": edges}

