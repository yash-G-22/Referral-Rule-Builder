/**
 * Referral Rule Flow Builder
 * 
 * A visual flow builder for creating referral rules with:
 * - Drag and drop node creation
 * - Node connections with bezier curves
 * - Property editing panel
 * - Export to JSON rule format
 * - AI natural language to rule generation
 */

// ==========================================
// State Management
// ==========================================

const state = {
    nodes: [],
    connections: [],
    selectedNode: null,
    connecting: null, // { nodeId, portType }
    nextNodeId: 1,
    dragOffset: { x: 0, y: 0 }
};

// ==========================================
// Node Templates
// ==========================================

const nodeTemplates = {
    trigger: {
        referral_signup: { label: 'Referral Signup', icon: '🎯' },
        subscription_started: { label: 'Subscription Started', icon: '📝' },
        payment_received: { label: 'Payment Received', icon: '💰' }
    },
    condition: {
        'referrer.is_paid_user': {
            label: 'Is Paid User',
            icon: '🔷',
            field: 'referrer.is_paid_user',
            operators: ['equals', 'not_equals'],
            valueType: 'boolean'
        },
        'referred.subscription_plan': {
            label: 'Subscription Plan',
            icon: '🔷',
            field: 'referred.subscription_plan',
            operators: ['equals', 'not_equals', 'in'],
            valueType: 'select',
            options: ['free', 'basic', 'premium', 'enterprise']
        },
        'referrer.tier': {
            label: 'User Tier',
            icon: '🔷',
            field: 'referrer.tier',
            operators: ['equals', 'not_equals'],
            valueType: 'select',
            options: ['standard', 'silver', 'gold', 'VIP']
        },
        'payment.amount': {
            label: 'Payment Amount',
            icon: '🔷',
            field: 'payment.amount',
            operators: ['equals', 'greater_than', 'less_than', 'greater_than_or_equal'],
            valueType: 'number'
        }
    },
    action: {
        credit_reward: {
            label: 'Credit Reward',
            icon: '🎁',
            params: ['amount', 'currency', 'reward_type']
        },
        send_notification: {
            label: 'Send Notification',
            icon: '📧',
            params: ['channel', 'template']
        },
        update_status: {
            label: 'Update Status',
            icon: '📋',
            params: ['entity', 'status']
        }
    },
    logic: {
        AND: { label: 'AND Gate', icon: '➕' },
        OR: { label: 'OR Gate', icon: '⚡' }
    }
};

// ==========================================
// DOM Elements
// ==========================================

const canvas = document.getElementById('canvas');
const nodesLayer = document.getElementById('nodes-layer');
const connectionsLayer = document.getElementById('connections');
const propertiesPanel = document.getElementById('properties-content');
const exportModal = document.getElementById('export-modal');
const exportJson = document.getElementById('export-json');
const instructions = document.getElementById('instructions');

// ==========================================
// Event Listeners - Palette
// ==========================================

document.querySelectorAll('.palette-item').forEach(item => {
    item.addEventListener('dragstart', handlePaletteDragStart);
    item.addEventListener('dragend', handlePaletteDragEnd);
});

canvas.addEventListener('dragover', handleCanvasDragOver);
canvas.addEventListener('drop', handleCanvasDrop);
canvas.addEventListener('click', handleCanvasClick);

// Button handlers
document.getElementById('btn-clear').addEventListener('click', clearCanvas);
document.getElementById('btn-export').addEventListener('click', showExportModal);
document.getElementById('modal-close').addEventListener('click', hideExportModal);
document.getElementById('btn-copy').addEventListener('click', copyToClipboard);
document.getElementById('btn-generate').addEventListener('click', generateFromAI);

// ==========================================
// Drag and Drop - Palette to Canvas
// ==========================================

function handlePaletteDragStart(e) {
    e.dataTransfer.setData('application/json', JSON.stringify({
        nodeType: e.target.dataset.nodeType,
        trigger: e.target.dataset.trigger,
        field: e.target.dataset.field,
        action: e.target.dataset.action,
        logic: e.target.dataset.logic
    }));
    e.target.classList.add('dragging');
}

function handlePaletteDragEnd(e) {
    e.target.classList.remove('dragging');
}

function handleCanvasDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
}

function handleCanvasDrop(e) {
    e.preventDefault();

    const data = JSON.parse(e.dataTransfer.getData('application/json'));
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    createNode(data, x, y);

    // Hide instructions after first node is added
    instructions.classList.add('hidden');
}

// ==========================================
// Node Creation
// ==========================================

function createNode(data, x, y) {
    const nodeId = `node-${state.nextNodeId++}`;
    const nodeType = data.nodeType;

    let template, subType;

    switch (nodeType) {
        case 'trigger':
            template = nodeTemplates.trigger[data.trigger];
            subType = data.trigger;
            break;
        case 'condition':
            template = nodeTemplates.condition[data.field];
            subType = data.field;
            break;
        case 'action':
            template = nodeTemplates.action[data.action];
            subType = data.action;
            break;
        case 'logic':
            template = nodeTemplates.logic[data.logic];
            subType = data.logic;
            break;
    }

    if (!template) return;

    // Create node state
    const node = {
        id: nodeId,
        type: nodeType,
        subType: subType,
        x: x - 90, // Center on cursor
        y: y - 30,
        template: template,
        config: getDefaultConfig(nodeType, subType)
    };

    state.nodes.push(node);

    // Create DOM element
    renderNode(node);

    return node;
}

function getDefaultConfig(nodeType, subType) {
    const config = {};

    if (nodeType === 'condition') {
        const template = nodeTemplates.condition[subType];
        config.field = template.field;
        config.operator = template.operators[0];
        config.value = template.valueType === 'boolean' ? true :
            template.valueType === 'number' ? 0 :
                template.options ? template.options[0] : '';
    }

    if (nodeType === 'action') {
        if (subType === 'credit_reward') {
            config.amount = 100;
            config.currency = 'INR';
            config.reward_type = 'voucher';
        } else if (subType === 'send_notification') {
            config.channel = 'email';
            config.template = 'reward_credited';
        }
    }

    return config;
}

function renderNode(node) {
    const el = document.createElement('div');
    el.className = 'flow-node';
    el.id = node.id;
    el.dataset.type = node.type;
    el.style.left = `${node.x}px`;
    el.style.top = `${node.y}px`;

    // Build node HTML
    el.innerHTML = `
        <div class="node-header">
            <span class="node-icon">${node.template.icon}</span>
            <span class="node-label">${node.template.label}</span>
        </div>
        <div class="node-body">
            ${renderNodeBody(node)}
        </div>
        <div class="node-ports">
            ${node.type !== 'trigger' ? '<div class="port input" data-port="input"></div>' : '<div></div>'}
            ${node.type !== 'action' ? '<div class="port output" data-port="output"></div>' : '<div></div>'}
        </div>
    `;

    // Event listeners
    el.addEventListener('mousedown', (e) => handleNodeMouseDown(e, node));
    el.addEventListener('click', (e) => handleNodeClick(e, node));

    // Port click handlers
    el.querySelectorAll('.port').forEach(port => {
        port.addEventListener('click', (e) => handlePortClick(e, node, port.dataset.port));
    });

    nodesLayer.appendChild(el);
}

function renderNodeBody(node) {
    if (node.type === 'condition') {
        const template = nodeTemplates.condition[node.subType];
        return `
            <div class="node-field">
                <label>Operator</label>
                <select class="node-operator" data-config="operator">
                    ${template.operators.map(op =>
            `<option value="${op}" ${node.config.operator === op ? 'selected' : ''}>${op}</option>`
        ).join('')}
                </select>
            </div>
            <div class="node-field">
                <label>Value</label>
                ${renderValueInput(template, node.config.value)}
            </div>
        `;
    }

    if (node.type === 'action' && node.subType === 'credit_reward') {
        return `
            <div class="node-field">
                <label>Amount</label>
                <input type="number" class="node-value" data-config="amount" value="${node.config.amount || 100}">
            </div>
            <div class="node-field">
                <label>Type</label>
                <select class="node-value" data-config="reward_type">
                    <option value="voucher" ${node.config.reward_type === 'voucher' ? 'selected' : ''}>Voucher</option>
                    <option value="cash" ${node.config.reward_type === 'cash' ? 'selected' : ''}>Cash</option>
                    <option value="points" ${node.config.reward_type === 'points' ? 'selected' : ''}>Points</option>
                </select>
            </div>
        `;
    }

    if (node.type === 'logic') {
        return `<div style="text-align: center; padding: 8px; color: var(--text-muted);">
            Combine ${node.subType === 'AND' ? 'all' : 'any'} inputs
        </div>`;
    }

    return '';
}

function renderValueInput(template, value) {
    if (template.valueType === 'boolean') {
        return `
            <select class="node-value" data-config="value">
                <option value="true" ${value === true ? 'selected' : ''}>True</option>
                <option value="false" ${value === false ? 'selected' : ''}>False</option>
            </select>
        `;
    }

    if (template.valueType === 'select' && template.options) {
        return `
            <select class="node-value" data-config="value">
                ${template.options.map(opt =>
            `<option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>`
        ).join('')}
            </select>
        `;
    }

    if (template.valueType === 'number') {
        return `<input type="number" class="node-value" data-config="value" value="${value || 0}">`;
    }

    return `<input type="text" class="node-value" data-config="value" value="${value || ''}">`;
}

// ==========================================
// Node Interactions
// ==========================================

function handleNodeMouseDown(e, node) {
    if (e.target.closest('.port') || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
        return;
    }

    e.preventDefault();

    const el = document.getElementById(node.id);
    const rect = el.getBoundingClientRect();

    state.dragOffset = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
    };

    const handleMouseMove = (e) => {
        const canvasRect = canvas.getBoundingClientRect();
        node.x = e.clientX - canvasRect.left - state.dragOffset.x;
        node.y = e.clientY - canvasRect.top - state.dragOffset.y;

        el.style.left = `${node.x}px`;
        el.style.top = `${node.y}px`;

        updateConnections();
    };

    const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
}

function handleNodeClick(e, node) {
    e.stopPropagation();

    // Deselect previous
    if (state.selectedNode) {
        const prevEl = document.getElementById(state.selectedNode.id);
        if (prevEl) prevEl.classList.remove('selected');
    }

    // Select new
    state.selectedNode = node;
    document.getElementById(node.id).classList.add('selected');

    // Update properties panel
    renderPropertiesPanel(node);
}

function handleCanvasClick(e) {
    if (e.target === canvas || e.target === nodesLayer) {
        // Deselect
        if (state.selectedNode) {
            const el = document.getElementById(state.selectedNode.id);
            if (el) el.classList.remove('selected');
            state.selectedNode = null;
        }

        state.connecting = null;
        canvas.classList.remove('connecting');

        renderPropertiesPanel(null);
    }
}

// ==========================================
// Connections
// ==========================================

function handlePortClick(e, node, portType) {
    e.stopPropagation();

    if (!state.connecting) {
        // Start connection
        state.connecting = { nodeId: node.id, portType };
        canvas.classList.add('connecting');
        e.target.classList.add('connecting');
    } else {
        // Complete connection
        if (state.connecting.nodeId !== node.id &&
            state.connecting.portType !== portType) {

            const fromNode = state.connecting.portType === 'output' ?
                state.connecting.nodeId : node.id;
            const toNode = state.connecting.portType === 'output' ?
                node.id : state.connecting.nodeId;

            // Check if connection already exists
            const exists = state.connections.some(
                c => c.from === fromNode && c.to === toNode
            );

            if (!exists) {
                state.connections.push({ from: fromNode, to: toNode });
                updateConnections();

                // Mark ports as connected
                document.querySelector(`#${fromNode} .port.output`).classList.add('connected');
                document.querySelector(`#${toNode} .port.input`).classList.add('connected');
            }
        }

        // Reset connecting state
        document.querySelectorAll('.port.connecting').forEach(p =>
            p.classList.remove('connecting')
        );
        state.connecting = null;
        canvas.classList.remove('connecting');
    }
}

function updateConnections() {
    connectionsLayer.innerHTML = '';

    state.connections.forEach(conn => {
        const fromEl = document.querySelector(`#${conn.from} .port.output`);
        const toEl = document.querySelector(`#${conn.to} .port.input`);

        if (fromEl && toEl) {
            const fromRect = fromEl.getBoundingClientRect();
            const toRect = toEl.getBoundingClientRect();
            const canvasRect = canvas.getBoundingClientRect();

            const x1 = fromRect.left + fromRect.width / 2 - canvasRect.left;
            const y1 = fromRect.top + fromRect.height / 2 - canvasRect.top;
            const x2 = toRect.left + toRect.width / 2 - canvasRect.left;
            const y2 = toRect.top + toRect.height / 2 - canvasRect.top;

            // Create bezier curve path
            const dx = Math.abs(x2 - x1) * 0.5;
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            path.setAttribute('d', `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`);
            path.dataset.from = conn.from;
            path.dataset.to = conn.to;

            // Click to delete
            path.style.pointerEvents = 'stroke';
            path.style.cursor = 'pointer';
            path.addEventListener('click', () => deleteConnection(conn));

            connectionsLayer.appendChild(path);
        }
    });
}

function deleteConnection(conn) {
    state.connections = state.connections.filter(
        c => !(c.from === conn.from && c.to === conn.to)
    );
    updateConnections();
}

// ==========================================
// Properties Panel
// ==========================================

function renderPropertiesPanel(node) {
    if (!node) {
        propertiesPanel.innerHTML = '<p class="hint">Select a node to edit its properties</p>';
        return;
    }

    let html = `
        <div class="property-group">
            <label>Type</label>
            <input type="text" value="${node.type.toUpperCase()}" disabled>
        </div>
        <div class="property-group">
            <label>Name</label>
            <input type="text" value="${node.template.label}" disabled>
        </div>
    `;

    if (node.type === 'condition') {
        html += `
            <div class="property-group">
                <label>Field</label>
                <input type="text" value="${node.config.field}" disabled>
            </div>
            <div class="property-group">
                <label>Operator</label>
                <input type="text" value="${node.config.operator}" id="prop-operator">
            </div>
            <div class="property-group">
                <label>Value</label>
                <input type="text" value="${node.config.value}" id="prop-value">
            </div>
        `;
    }

    if (node.type === 'action') {
        Object.entries(node.config).forEach(([key, value]) => {
            html += `
                <div class="property-group">
                    <label>${key.charAt(0).toUpperCase() + key.slice(1)}</label>
                    <input type="text" value="${value}" id="prop-${key}">
                </div>
            `;
        });
    }

    html += `
        <div class="property-group">
            <button class="btn btn-secondary" onclick="deleteNode('${node.id}')" style="width: 100%;">
                🗑️ Delete Node
            </button>
        </div>
    `;

    propertiesPanel.innerHTML = html;
}

function deleteNode(nodeId) {
    // Remove from state
    state.nodes = state.nodes.filter(n => n.id !== nodeId);
    state.connections = state.connections.filter(
        c => c.from !== nodeId && c.to !== nodeId
    );

    // Remove from DOM
    const el = document.getElementById(nodeId);
    if (el) el.remove();

    // Update connections
    updateConnections();

    // Clear selection
    state.selectedNode = null;
    renderPropertiesPanel(null);
}

// ==========================================
// Export
// ==========================================

function showExportModal() {
    const rule = buildRuleJSON();
    exportJson.textContent = JSON.stringify(rule, null, 2);
    exportModal.classList.remove('hidden');
}

function hideExportModal() {
    exportModal.classList.add('hidden');
}

function copyToClipboard() {
    navigator.clipboard.writeText(exportJson.textContent)
        .then(() => {
            const btn = document.getElementById('btn-copy');
            const originalText = btn.textContent;
            btn.textContent = '✓ Copied!';
            setTimeout(() => btn.textContent = originalText, 2000);
        });
}

function buildRuleJSON() {
    // Find trigger node
    const triggerNode = state.nodes.find(n => n.type === 'trigger');

    // Find condition nodes
    const conditionNodes = state.nodes.filter(n => n.type === 'condition');

    // Find action nodes
    const actionNodes = state.nodes.filter(n => n.type === 'action');

    // Find logic nodes
    const logicNodes = state.nodes.filter(n => n.type === 'logic');

    // Build conditions
    let conditions;
    if (conditionNodes.length === 0) {
        conditions = { field: "event.occurred", operator: "is_true" };
    } else if (conditionNodes.length === 1) {
        conditions = {
            field: conditionNodes[0].config.field,
            operator: conditionNodes[0].config.operator,
            value: conditionNodes[0].config.value
        };
    } else {
        // Check for logic gate
        const logicOperator = logicNodes.length > 0 ? logicNodes[0].subType : 'AND';
        conditions = {
            operator: logicOperator,
            conditions: conditionNodes.map(node => ({
                field: node.config.field,
                operator: node.config.operator,
                value: node.config.value
            }))
        };
    }

    // Build actions
    const actions = actionNodes.map(node => ({
        type: node.subType,
        params: { ...node.config }
    }));

    // Build rule
    return {
        id: `rule-${Date.now()}`,
        name: "Generated Rule",
        description: "Rule created with visual flow builder",
        version: 1,
        is_active: true,
        priority: 0,
        trigger: triggerNode ? triggerNode.subType : 'referral_signup',
        conditions: conditions,
        actions: actions.length > 0 ? actions : [{ type: 'credit_reward', params: { amount: 100, currency: 'INR' } }]
    };
}

// ==========================================
// AI Generation
// ==========================================

async function generateFromAI() {
    const input = document.getElementById('ai-input').value.trim();
    if (!input) return;

    const btn = document.getElementById('btn-generate');
    const originalText = btn.textContent;
    btn.textContent = 'Generating...';
    btn.disabled = true;

    try {
        // Use local pattern matching (in production, call backend API)
        const rule = parseNaturalLanguage(input);

        // Clear canvas
        clearCanvas();

        // Create nodes from rule
        generateNodesFromRule(rule);

        btn.textContent = '✓ Generated!';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 2000);

    } catch (error) {
        console.error('Generation error:', error);
        btn.textContent = 'Error!';
        setTimeout(() => {
            btn.textContent = originalText;
            btn.disabled = false;
        }, 2000);
    }
}

function parseNaturalLanguage(text) {
    const textLower = text.toLowerCase();

    // Detect trigger
    let trigger = 'referral_signup';
    if (textLower.includes('subscri')) trigger = 'subscription_started';
    else if (textLower.includes('payment') || textLower.includes('pay')) trigger = 'payment_received';

    // Detect conditions
    const conditions = [];

    if (textLower.includes('paid user') || textLower.includes('paid member')) {
        conditions.push({
            field: 'referrer.is_paid_user',
            operator: 'equals',
            value: true
        });
    }

    if (textLower.includes('premium')) {
        conditions.push({
            field: 'referred.subscription_plan',
            operator: 'equals',
            value: 'premium'
        });
    }

    if (textLower.includes('vip')) {
        conditions.push({
            field: 'referrer.tier',
            operator: 'equals',
            value: 'VIP'
        });
    }

    // Detect amount
    let amount = 100;
    const amountMatch = text.match(/(?:₹|rs\.?|inr|rupees?)\s*(\d+)/i) ||
        text.match(/(\d+)\s*(?:₹|rs\.?|inr|rupees?)/i);
    if (amountMatch) {
        amount = parseInt(amountMatch[1]);
    }

    // Detect reward type
    let rewardType = 'voucher';
    if (textLower.includes('cash')) rewardType = 'cash';
    else if (textLower.includes('point')) rewardType = 'points';

    return {
        trigger,
        conditions: conditions.length > 0 ? conditions : [{ field: 'referred.signup_completed', operator: 'is_true' }],
        actions: [{
            type: 'credit_reward',
            params: { amount, currency: 'INR', reward_type: rewardType }
        }]
    };
}

function generateNodesFromRule(rule) {
    let yOffset = 80;

    // Create trigger node
    createNode({
        nodeType: 'trigger',
        trigger: rule.trigger
    }, 100, yOffset);

    // Create condition nodes
    rule.conditions.forEach((cond, i) => {
        if (cond.field && nodeTemplates.condition[cond.field]) {
            const node = createNode({
                nodeType: 'condition',
                field: cond.field
            }, 350, yOffset + i * 120);

            // Update config
            if (node) {
                node.config.operator = cond.operator;
                node.config.value = cond.value;
            }
        }
    });

    // Create AND gate if multiple conditions
    if (rule.conditions.length > 1) {
        createNode({
            nodeType: 'logic',
            logic: 'AND'
        }, 550, yOffset + 60);
    }

    // Create action nodes
    rule.actions.forEach((action, i) => {
        const node = createNode({
            nodeType: 'action',
            action: action.type
        }, rule.conditions.length > 1 ? 750 : 550, yOffset + i * 120);

        // Update config
        if (node && action.params) {
            Object.assign(node.config, action.params);
        }
    });

    // Hide instructions
    instructions.classList.add('hidden');
}

// ==========================================
// Clear Canvas
// ==========================================

function clearCanvas() {
    state.nodes = [];
    state.connections = [];
    state.selectedNode = null;
    state.connecting = null;

    nodesLayer.innerHTML = '';
    connectionsLayer.innerHTML = '';

    renderPropertiesPanel(null);
    instructions.classList.remove('hidden');
}

// Initialize
console.log('🔗 Referral Rule Flow Builder initialized');
