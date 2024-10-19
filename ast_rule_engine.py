from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client['rule_engine_db']

# Data structure to represent AST Nodes
class Node:
    def __init__(self, node_type, left=None, right=None, value=None):
        self.type = node_type  # 'operator' or 'operand'
        self.left = left  # Left child node
        self.right = right  # Right child node
        self.value = value  # Value for operand nodes (conditions)

# Function to create AST from rule string
def create_ast(rule_string):
    rule_string = rule_string.strip()
    if "AND" in rule_string:
        left_rule = rule_string.split(" AND ")[0].strip()
        right_rule = rule_string.split(" AND ")[1].strip()
        return Node("operator", create_ast(left_rule), create_ast(right_rule), "AND")
    elif "OR" in rule_string:
        left_rule = rule_string.split(" OR ")[0].strip()
        right_rule = rule_string.split(" OR ")[1].strip()
        return Node("operator", create_ast(left_rule), create_ast(right_rule), "OR")
    else:
        return Node("operand", value=rule_string)

# Function to evaluate the AST against user data
def evaluate_ast(ast, data):
    if ast.type == "operand":
        condition = ast.value
        field, operator, threshold = condition.split(" ")

        value = data.get(field)
        if value is None:
            return False  # Field is not in user data

        try:
            threshold = float(threshold)
        except ValueError:
            threshold = threshold.strip("'\"")  # Strip quotes for string comparison

        if isinstance(value, (int, float)) and isinstance(threshold, (int, float)):
            if operator == ">":
                return value > threshold
            elif operator == "<":
                return value < threshold
            elif operator == "=":
                return value == threshold
        else:
            if operator == "=":
                return str(value) == str(threshold)

        return False

    elif ast.type == "operator":
        left_eval = evaluate_ast(ast.left, data)
        right_eval = evaluate_ast(ast.right, data)
        if ast.value == "AND":
            return left_eval and right_eval
        elif ast.value == "OR":
            return left_eval or right_eval
        return None

# Function to combine multiple ASTs
def combine_rules(rules, operator="AND"):
    if len(rules) == 1:
        return rules[0]
    
    combined_ast = rules[0]
    for rule in rules[1:]:
        combined_ast = Node("operator", combined_ast, rule, operator)
    
    return combined_ast

# Route to render the homepage
@app.route('/')
def index():
    return render_template('index.html')

# Route to render the create rule page
@app.route('/create_rule_page')
def create_rule_page():
    return render_template('create_rule.html')

# Route to render the view rules page
@app.route('/view_rules')
def view_rules():
    return render_template('view_rules.html')

# Route to render the evaluate rule page
@app.route('/evaluate_rule_page')
def evaluate_rule_page():
    return render_template('evaluate_rule.html')

# API to create a rule and store it in the database
@app.route('/create_rule', methods=['POST'])
def create_rule():
    rule_string = request.form['rule']
    rule_data = {
        "rule_string": rule_string,
    }
    result = db.rules.insert_one(rule_data)
    return jsonify({"status": "Rule created successfully", "rule": {"_id": str(result.inserted_id), "rule": rule_string}}), 201

# API to get all rules from the database
@app.route('/rules', methods=['GET'])
def get_rules():
    rules = list(db.rules.find({}))
    for rule in rules:
        rule['_id'] = str(rule['_id'])
    return jsonify(rules), 200

# API to combine rules
@app.route('/combine_rules', methods=['POST'])
def combine_multiple_rules():
    rule_ids = request.json['rule_ids']  # List of rule IDs to combine
    operator = request.json.get('operator', 'AND')  # Default to "AND" if no operator is provided

    # Fetch all rules by their IDs
    rules = []
    for rule_id in rule_ids:
        rule_obj_id = ObjectId(rule_id)
        rule = db.rules.find_one({"_id": rule_obj_id})
        if rule:
            rule_ast = create_ast(rule['rule_string'])
            rules.append(rule_ast)

    # Combine the rules into a single AST
    combined_ast = combine_rules(rules, operator)

    return jsonify({"status": "Rules combined successfully", "operator": operator}), 200

# API to evaluate a rule against user data
@app.route('/evaluate_rule/<rule_id>', methods=['POST'])
def evaluate_rule(rule_id):
    try:
        rule_obj_id = ObjectId(rule_id)
    except Exception:
        return jsonify({"error": "Invalid Rule ID format"}), 400

    rule = db.rules.find_one({"_id": rule_obj_id})
    if not rule:
        return jsonify({"error": "Rule not found"}), 404

    rule_string = rule['rule_string']
    ast = create_ast(rule_string)

    # Get user data from request in JSON format
    user_data = request.json
    if not user_data:
        return jsonify({"error": "User data not provided"}), 400

    try:
        result = evaluate_ast(ast, user_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"result": result}), 200

# Main entry point
if __name__ == '__main__':
    app.run(debug=True)

