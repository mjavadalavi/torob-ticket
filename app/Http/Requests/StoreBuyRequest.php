<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\Rule;
use Illuminate\Foundation\Http\FormRequest;

class StoreBuyRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, Rule|array|string>
     */
    public function rules(): array
    {
        return [
            'reserve_id' => 'required|integer|min:0',
            'passengers' => 'required|array|min:3'
        ];
    }

    public function messages(): array
    {
        return [
            'reserve_id.required' => 'a integer of identity reserved values is required.',
            'passengers.required' => 'an array of passengers.',
        ];
    }
}
