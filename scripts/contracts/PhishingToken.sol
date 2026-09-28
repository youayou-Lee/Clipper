// SPDX-License-Identifier: MIT
// 演示用最小 ERC-20(仅本地 Anvil;标准 OpenZeppelin 写法的极简版)。
pragma solidity ^0.8.24;

contract PhishingToken {
    string public name = "Free Airdrop Token";
    string public symbol = "AIRDROP";
    uint8 public constant decimals = 18;
    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor() {
        _mint(msg.sender, 1_000_000 ether); // 部署者(演示中即"项目方")全部铸出
    }

    function approve(address spender, uint256 value) external returns (bool) {
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transfer(address to, uint256 value) external returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= value, "insufficient allowance");
        if (allowed != type(uint256).max) {
            allowance[from][msg.sender] = allowed - value;
        }
        _transfer(from, to, value);
        return true;
    }

    function permit(address owner, address spender, uint256 value, uint256 deadline,
                    uint8 v, bytes32 r, bytes32 s) external {
        require(deadline >= block.timestamp, "expired");
        bytes32 digest = keccak256(abi.encodePacked(
            "\x19\x01",
            keccak256(abi.encode(
                keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
                keccak256(bytes("PhishingToken")), keccak256(bytes("1")),
                block.chainid, address(this))),
            keccak256(abi.encode(
                keccak256("Permit(address owner,address spender,uint256 value,uint256 deadline,uint256 nonce)"),
                owner, spender, value, deadline, nonces[owner]++))));
        require(ecrecover(digest, v, r, s) == owner, "invalid signature");
        allowance[owner][spender] = value;
        emit Approval(owner, spender, value);
    }

    mapping(address => uint256) public nonces;

    function _transfer(address from, address to, uint256 value) internal {
        require(balanceOf[from] >= value, "insufficient balance");
        balanceOf[from] -= value;
        balanceOf[to] += value;
        emit Transfer(from, to, value);
    }

    function _mint(address to, uint256 value) internal {
        totalSupply += value;
        balanceOf[to] += value;
        emit Transfer(address(0), to, value);
    }
}
