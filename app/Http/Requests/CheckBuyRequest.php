<?php

namespace App\Http\Requests;

use Illuminate\Contracts\Validation\Rule;
use Illuminate\Foundation\Http\FormRequest;

class CheckBuyRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return false;
    }

    /**
     * Get the validation rules that apply to the request.
     *
     * @return array<string, Rule|array|string>
     */
    public function rules(): array
    {
        return [
            'action' => 'required|integer',
            'reserve_id' => 'int',
            'search_hash' => 'string',
            'ticket_id' => 'int'
        ];
    }

    public function messages(): array
    {
        return [
            'action.required' => 'a str action such as search, reserve, ticket of operations are required.',
        ];
    }
}
