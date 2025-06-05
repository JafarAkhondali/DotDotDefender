import math


class CVSS:
    """
    Based on https://www.first.org/cvss/v3.1/specification-document
    AND ChatGPT :-O

    # Example of setting up and using the CVSS class
    # cvss = CVSS()
    # cvss.set_metric('AV', 'N')
    # cvss.set_metric('AC', 'L')
    # cvss.set_metric('PR', 'N')
    # cvss.set_metric('UI', 'N')
    # cvss.set_metric('S', 'U')
    # cvss.set_metric('C', 'H')
    # cvss.set_metric('I', 'N')
    # cvss.set_metric('A', 'H')
    #
    # print("Vector String:", cvss.get_vector_string())
    # print("Base Score:", cvss.calculate_base_score())
    # print("Severity:", cvss.get_severity())

    """
    def __init__(self):
        self.metrics = {
            'AV': None,  # Attack Vector
            'AC': None,  # Attack Complexity
            'PR': None,  # Privileges Required
            'UI': None,  # User Interaction
            'S': None,  # Scope
            'C': None,  # Confidentiality
            'I': None,  # Integrity
            'A': None  # Availability
        }
        self.weights = {
            'AV': {'N': 0.85, 'A': 0.62, 'L': 0.55, 'P': 0.2},
            'AC': {'L': 0.77, 'H': 0.44},
            'PR': {'N': 0.85, 'L': 0.62, 'H': 0.27},
            'UI': {'N': 0.85, 'R': 0.62},
            'S': {'U': 6.42, 'C': 7.52},
            'C': {'N': 0, 'L': 0.22, 'H': 0.56},
            'I': {'N': 0, 'L': 0.22, 'H': 0.56},
            'A': {'N': 0, 'L': 0.22, 'H': 0.56},
        }

    def set_metric(self, key, value):
        if key in self.metrics and value in self.weights[key]:
            self.metrics[key] = value
        else:
            raise ValueError("Invalid metric key or value")

    def calculate_base_score(self):
        if None in self.metrics.values():
            raise ValueError("Not all CVSS metrics have been set")

        impact_subscore = 1 - ((1 - self.weights['C'][self.metrics['C']]) *
                               (1 - self.weights['I'][self.metrics['I']]) *
                               (1 - self.weights['A'][self.metrics['A']]))

        if self.metrics['S'] == 'U':
            impact = 6.42 * impact_subscore
        else:
            impact = 7.52 * (impact_subscore - 0.029) - 3.25 * math.pow(impact_subscore - 0.02, 15)

        exploitability = 8.22 * self.weights['AV'][self.metrics['AV']] * self.weights['AC'][self.metrics['AC']] * \
                         self.weights['PR'][self.metrics['PR']] * self.weights['UI'][self.metrics['UI']]

        if impact_subscore <= 0:
            return 0
        else:
            return round(min((impact + exploitability), 10) if self.metrics['S'] == 'U' else min(
                1.08 * (impact + exploitability), 10), 1)

    def get_vector_string(self):
        return f"CVSS:3.1/" + "/".join([f"{key}:{value}" for key, value in self.metrics.items()])

    def get_severity(self):
        base_score = self.calculate_base_score()
        if base_score == 0:
            return 'None'
        elif base_score <= 3.9:
            return 'Low'
        elif base_score <= 6.9:
            return 'Medium'
        elif base_score <= 8.9:
            return 'High'
        else:
            return 'Critical'