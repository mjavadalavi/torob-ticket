<?php

namespace App\Http\Controllers\API;

use App\Classes\Encoding;
use App\Classes\ProjectResource;
use App\Enums\ReservationStatus;
use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\CancelReserveRequest;
use App\Http\Requests\StoreReserveRequest;
use App\Models\Reservation;
use Illuminate\Http\JsonResponse as JsonResponseAlias;
use Symfony\Component\HttpFoundation\Response;

class ReserveController extends Controller
{
    /**
     * @OA\Post(
     *      path="/Reserve",
     *      operationId="storeReserveRequest",
     *      tags={"StoreReserve"},
     *      summary="Store new Reserve",
     *      description="Returns json of result storing data",
     *      @OA\RequestBody(
     *          required=true,
     *          @OA\JsonContent(ref="#/components/schemas/StoreReserveRequest")
     *      ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          @OA\JsonContent(ref="#/components/schemas/Reservation")
     *       ),
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request"
     *      )
     * )
     */
    public function store(StoreReserveRequest $request)
    {
        if ($request->validated()){
            $search_id = explode('|',Encoding::base64url_decode($request->input("search_id")));
            $passenger_count = $request->input("passenger_count");
            $chairs = $request->input("chairs");
            $reserve = new Reservation();
            $reserve->ws_id = $search_id[0];
            $reserve->chair_id = $search_id[1];
            $reserve->passenger_count = $passenger_count;
            $reserve->chairs = $chairs;
            $reserve->save();
            return response()
                ->json(['status' => Status::Success , "code" => StatusCode::Success])
                ->setStatusCode(Response::HTTP_ACCEPTED)
                ->header('Content-Type', 'application/json');
        }else{
            return response()
                ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *      path="/Cancellation",
     *      operationId="CancelReserveRequest",
     *      tags={"CancelReserve"},
     *      summary="Cancel a Reserve",
     *      description="Returns json of result cancelling.",
     *      @OA\RequestBody(
     *          required=true,
     *          @OA\JsonContent(ref="#/components/schemas/CancelReserveRequest")
     *      ),
     *      @OA\Response(
     *          response=201,
     *          description="Successful operation",
     *          @OA\JsonContent(ref="#/components/schemas/Reservation")
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found"
     *      )
     *      @OA\Response(
     *          response=400,
     *          description="Bad Request"
     *      )
     * )
     */
    public function cancellation(CancelReserveRequest $request)
    {
        if ($request->validated()){
            $reserve = Reservation::find($request->input("reserve_id"));
            if (count($reserve) > 0){
                $reserve->status = ReservationStatus::Cancel;
                $reserve->chairs()->chairs[] = $request->chairs;
                $reserve->save();
                $response = ['status' => Status::Success , "code" => StatusCode::Success];
                $response_code = Response::HTTP_OK;
            }else{
                $response = ['status' => Status::Failed , "code" => StatusCode::Failed];
                $response_code = Response::HTTP_NOT_FOUND;
            }
        }else{
            $response = ['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed];
            $response_code = Response::HTTP_BAD_REQUEST;
        }
        return (new ProjectResource($response))
            ->response()
            ->setStatusCode($response_code)
            ->header('Content-Type', 'application/json');
    }
}
