uint MixWord(uint word, uint key) {
    if (word == 0u) { return key; }
    word += key;
    word -= 3u;
    word *= 0x85EBCA6Bu;
    word &= 0x7FFFFFFFu;
    word |= 1u;
    word ^= word >> 13u;
    word <<= key;
    word >>= key >> 5u;
    if (word < 0x80000000u) { return word; }
    return word ^ 0x9E3779B9u;
}

float4 main(float4 input : COLOR0) : SV_Target {
    uint word = MixWord(asuint(input.x), asuint(input.y));
    if (word == 0u) { return input; }
    return float4(asfloat(word), input.y, input.z, input.w);
}
