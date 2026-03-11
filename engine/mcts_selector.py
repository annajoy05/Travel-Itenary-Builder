import math
import random

class MCTSNode:
    def __init__(self, state, parent=None, action=None, all_place_names=None):
        self.state = state  # List of attraction names
        self.parent = parent
        self.action = action  # The attraction added to get to this state
        self.children = []
        self.wins = 0
        self.visits = 0
        self.untried_actions = [name for name in all_place_names if name not in state] if all_place_names else []

    def select_child(self):
        # UCB1 Selection formula
        if not self.children:
            return None
        return max(self.children, key=lambda c: (c.wins / c.visits) + 1.41 * math.sqrt(math.log(self.visits) / c.visits))

    def add_child(self, action, state, all_place_names):
        child = MCTSNode(state, parent=self, action=action, all_place_names=all_place_names)
        if action in self.untried_actions:
            self.untried_actions.remove(action)
        self.children.append(child)
        return child

    def update(self, reward):
        self.visits += 1
        self.wins += reward

def select_best_attractions(all_attractions, budget, max_places=6, iterations=500):
    """
    Uses MCTS to select a subset of attractions that fits the budget and maximizes rating.
    """
    if not all_attractions:
        return []

    place_names = [a['place_name'] for a in all_attractions]
    attr_map = {a['place_name']: a for a in all_attractions}
    
    root = MCTSNode(state=[], all_place_names=list(place_names))

    for _ in range(iterations):
        node = root
        
        # 1. Selection
        while not node.untried_actions and node.children:
            node = node.select_child()
            if not node: break
            
        # 2. Expansion
        if node and node.untried_actions and len(node.state) < max_places:
            action = random.choice(node.untried_actions)
            new_state = node.state + [action]
            node = node.add_child(action, new_state, place_names)
            
        # 3. Simulation (Rollout)
        state = list(node.state)
        # Randomly complete the set
        sim_max = random.randint(min(3, len(place_names)), max_places)
        while len(state) < sim_max:
            possible = [name for name in place_names if name not in state]
            if not possible: break
            state.append(random.choice(possible))
            
        # Evaluation (Reward function)
        total_rating = sum(attr_map[name]['avg_rating'] for name in state)
        total_fee = sum(attr_map[name]['avg_fee'] for name in state)
        
        if total_fee > budget:
            reward = 0  # Invalid path
        else:
            # Reward: Average rating multiplied by a small factor of the path length 
            # Exponentially reward higher ratings and discourage low ones
            avg_rating = total_rating / len(state) if state else 0
            reward = (avg_rating ** 2) * (1 + 0.2 * len(state))
            
        # 4. Backpropagation
        curr = node
        while curr:
            curr.update(reward)
            curr = curr.parent
            
    # Extraction: Return the path leading to the most visited leaf/node
    best_path = []
    curr = root
    while curr.children:
        # Greedily pick the child with most visits
        curr = max(curr.children, key=lambda c: c.visits)
        best_path.append(curr.action)
        if len(best_path) >= max_places:
            break
            
    return [attr_map[name] for name in best_path]

if __name__ == '__main__':
    # Test stub
    mock_data = [
        {'place_name': 'A', 'avg_rating': 5, 'avg_fee': 1000},
        {'place_name': 'B', 'avg_rating': 4, 'avg_fee': 200},
        {'place_name': 'C', 'avg_rating': 3, 'avg_fee': 100},
        {'place_name': 'D', 'avg_rating': 4.5, 'avg_fee': 500},
    ]
    selected = select_best_attractions(mock_data, budget=800)
    print("MCTS Selected:")
    for s in selected:
        print(f"- {s['place_name']} (Rating: {s['avg_rating']}, Fee: {s['avg_fee']})")
